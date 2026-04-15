// NPC Dialogue Client for Unity
// REST API client for communicating with the NPC Dialogue System server

using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

namespace NPCDialogue
{
    /// <summary>
    /// Main client for communicating with the NPC Dialogue API server.
    /// </summary>
    public class NPCDialogueClient : MonoBehaviour
    {
        [Header("Server Configuration")]
        [Tooltip("URL of the NPC Dialogue API server")]
        public string serverUrl = "http://localhost:8000";
        
        [Tooltip("Default model to use for generation")]
        public string defaultModel = "llama3.2:1b";
        
        [Tooltip("Default player ID")]
        public string defaultPlayerId = "player";
        
        [Header("Settings")]
        [Tooltip("Timeout for API requests in seconds")]
        public float requestTimeout = 30f;
        
        [Tooltip("Enable debug logging")]
        public bool debugLogging = true;
        
        // Events
        public event Action<string> OnResponseReceived;
        public event Action<string> OnError;
        public event Action<string> OnTokenReceived;
        public event Action OnServerConnected;
        public event Action OnServerDisconnected;
        
        // State
        private bool _isConnected = false;
        private Coroutine _connectionCheckCoroutine;
        
        #region Public API
        
        /// <summary>
        /// Check if the server is connected and available.
        /// </summary>
        public async Task<bool> CheckConnectionAsync()
        {
            try
            {
                var status = await GetAsync<StatusResponse>("/api/status");
                _isConnected = status != null && status.ollama_connected;
                
                if (_isConnected)
                    OnServerConnected?.Invoke();
                else
                    OnServerDisconnected?.Invoke();
                
                return _isConnected;
            }
            catch (Exception e)
            {
                LogDebug($"Connection check failed: {e.Message}");
                _isConnected = false;
                OnServerDisconnected?.Invoke();
                return false;
            }
        }
        
        /// <summary>
        /// Generate an NPC response to player input.
        /// </summary>
        /// <param name="npcName">Name of the NPC to talk to</param>
        /// <param name="playerInput">What the player says</param>
        /// <param name="playerId">Player identifier</param>
        /// <param name="gameState">Optional game state context</param>
        /// <returns>Generated NPC response</returns>
        public async Task<DialogueResponse> GenerateResponseAsync(
            string npcName,
            string playerInput,
            string playerId = null,
            Dictionary<string, object> gameState = null)
        {
            var request = new GenerateRequest
            {
                npc_name = npcName,
                player_input = playerInput,
                player_id = playerId ?? defaultPlayerId,
                game_state = gameState
            };
            
            try
            {
                var response = await PostAsync<DialogueResponse>("/api/dialogue/generate", request);
                OnResponseReceived?.Invoke(response.response);
                return response;
            }
            catch (Exception e)
            {
                OnError?.Invoke($"Failed to generate response: {e.Message}");
                throw;
            }
        }
        
        /// <summary>
        /// Generate an NPC response with streaming (real-time tokens).
        /// </summary>
        /// <param name="npcName">Name of the NPC</param>
        /// <param name="playerInput">Player's input</param>
        /// <param name="onToken">Callback for each token received</param>
        /// <param name="onComplete">Callback when generation is complete</param>
        /// <param name="playerId">Player identifier</param>
        /// <param name="gameState">Optional game state</param>
        public void GenerateResponseStream(
            string npcName,
            string playerInput,
            Action<string> onToken,
            Action<string> onComplete = null,
            string playerId = null,
            Dictionary<string, object> gameState = null)
        {
            StartCoroutine(GenerateResponseStreamCoroutine(
                npcName, playerInput, onToken, onComplete, playerId, gameState
            ));
        }
        
        /// <summary>
        /// Load a character from the server.
        /// </summary>
        public async Task<CharacterInfo> LoadCharacterAsync(
            string characterPath,
            string playerId = null)
        {
            var request = new LoadCharacterRequest
            {
                character_path = characterPath,
                player_id = playerId ?? defaultPlayerId
            };
            
            var response = await PostAsync<CharacterLoadResponse>("/api/characters/load", request);
            
            return new CharacterInfo
            {
                name = response.character_name,
                description = response.description
            };
        }
        
        /// <summary>
        /// Get list of available characters.
        /// </summary>
        public async Task<CharacterListResponse> ListCharactersAsync()
        {
            return await GetAsync<CharacterListResponse>("/api/characters");
        }
        
        /// <summary>
        /// Unload a character from memory.
        /// </summary>
        public async Task UnloadCharacterAsync(string npcName)
        {
            await DeleteAsync($"/api/characters/{npcName}");
        }
        
        /// <summary>
        /// Get relationship between NPC and player.
        /// </summary>
        public async Task<RelationshipInfo> GetRelationshipAsync(string npcName, string playerId = null)
        {
            playerId = playerId ?? defaultPlayerId;
            return await GetAsync<RelationshipInfo>($"/api/relationships/{npcName}/{playerId}");
        }
        
        /// <summary>
        /// Update relationship between NPC and player.
        /// </summary>
        public async Task<RelationshipUpdateResponse> UpdateRelationshipAsync(
            string npcName,
            int change,
            string reason = null,
            string playerId = null)
        {
            var request = new UpdateRelationshipRequest
            {
                npc_name = npcName,
                player_id = playerId ?? defaultPlayerId,
                change = change,
                reason = reason
            };
            
            return await PostAsync<RelationshipUpdateResponse>("/api/relationships/update", request);
        }
        
        /// <summary>
        /// Get all relationships for a player.
        /// </summary>
        public async Task<Dictionary<string, RelationshipData>> GetPlayerRelationshipsAsync(string playerId = null)
        {
            playerId = playerId ?? defaultPlayerId;
            return await GetAsync<Dictionary<string, RelationshipData>>($"/api/relationships/player/{playerId}");
        }
        
        /// <summary>
        /// Save conversation history.
        /// </summary>
        public async Task SaveHistoryAsync(string npcName, string playerId = null, string directory = "conversation_history")
        {
            var request = new SaveHistoryRequest
            {
                npc_name = npcName,
                player_id = playerId ?? defaultPlayerId,
                directory = directory
            };
            
            await PostAsync<SaveHistoryResponse>("/api/history/save", request);
        }
        
        /// <summary>
        /// Load conversation history.
        /// </summary>
        public async Task<LoadHistoryResponse> LoadHistoryAsync(string npcName, string playerId = null, string directory = "conversation_history")
        {
            var request = new LoadHistoryRequest
            {
                npc_name = npcName,
                player_id = playerId ?? defaultPlayerId,
                directory = directory
            };
            
            return await PostAsync<LoadHistoryResponse>("/api/history/load", request);
        }
        
        /// <summary>
        /// Generate response with structured game state.
        /// </summary>
        public async Task<DialogueResponse> GenerateWithGameStateAsync(
            string npcName,
            string playerInput,
            GameState gameState,
            string playerId = null)
        {
            var queryParams = new List<string>
            {
                $"npc_name={UnityWebRequest.EscapeURL(npcName)}",
                $"player_input={UnityWebRequest.EscapeURL(playerInput)}",
                $"player_id={UnityWebRequest.EscapeURL(playerId ?? defaultPlayerId)}"
            };
            
            if (!string.IsNullOrEmpty(gameState.location))
                queryParams.Add($"location={UnityWebRequest.EscapeURL(gameState.location)}");
            if (!string.IsNullOrEmpty(gameState.timeOfDay))
                queryParams.Add($"time_of_day={UnityWebRequest.EscapeURL(gameState.timeOfDay)}");
            if (!string.IsNullOrEmpty(gameState.currentQuest))
                queryParams.Add($"current_quest={UnityWebRequest.EscapeURL(gameState.currentQuest)}");
            if (gameState.playerHealth.HasValue)
                queryParams.Add($"player_health={gameState.playerHealth.Value}");
            if (gameState.playerGold.HasValue)
                queryParams.Add($"player_gold={gameState.playerGold.Value}");
            
            var queryString = string.Join("&", queryParams);
            return await PostAsync<DialogueResponse>($"/api/dialogue/generate-with-state?{queryString}", null);
        }
        
        /// <summary>
        /// Save all data (history + relationships).
        /// </summary>
        public async Task SaveAllAsync()
        {
            await PostAsync<SaveAllResponse>("/api/save-all", null);
        }

        /// <summary>
        /// Generate NPC response with automatic quest context injection.
        /// The server detects quest offers in NPC dialogue and handles acceptance.
        /// </summary>
        public async Task<DialogueResponse> GenerateWithQuestsAsync(
            string npcName,
            string playerInput,
            string playerId = null,
            Dictionary<string, object> gameState = null)
        {
            var request = new GenerateRequest
            {
                npc_name = npcName,
                player_input = playerInput,
                player_id = playerId ?? defaultPlayerId,
                game_state = gameState
            };

            try
            {
                var response = await PostAsync<DialogueResponse>("/api/dialogue/generate-with-quests", request);
                OnResponseReceived?.Invoke(response.response);
                return response;
            }
            catch (Exception e)
            {
                OnError?.Invoke($"Failed to generate response: {e.Message}");
                throw;
            }
        }

        /// <summary>
        /// Report a gameplay event to update quest progress.
        /// Call this when the player collects items, kills enemies, reaches locations, etc.
        /// This is the canonical way to update quest objectives from gameplay.
        /// </summary>
        public async Task<GameEventResponse> ReportGameEventAsync(
            string eventType,
            string target,
            int amount = 1,
            string location = null,
            string playerId = null)
        {
            var request = new GameEventRequest
            {
                event_type = eventType,
                target = target,
                amount = amount,
                location = location,
                player_id = playerId ?? defaultPlayerId
            };

            return await PostAsync<GameEventResponse>("/api/game/event", request);
        }

        /// <summary>
        /// Get available quests from an NPC.
        /// </summary>
        public async Task<QuestListResponse> GetQuestsAsync(string npcName, int playerLevel = 1)
        {
            return await GetAsync<QuestListResponse>($"/api/quests/npc/{npcName}?player_level={playerLevel}");
        }

        /// <summary>
        /// Accept a quest by ID.
        /// </summary>
        public async Task<QuestActionResponse> AcceptQuestAsync(string questId)
        {
            return await PostAsync<QuestActionResponse>($"/api/quests/{questId}/accept", null);
        }

        /// <summary>
        /// Complete a quest and claim rewards.
        /// </summary>
        public async Task<QuestCompleteResponse> CompleteQuestAsync(string questId)
        {
            return await PostAsync<QuestCompleteResponse>($"/api/quests/{questId}/complete", null);
        }

        /// <summary>
        /// Get all active quests for the player.
        /// </summary>
        public async Task<ActiveQuestsResponse> GetActiveQuestsAsync()
        {
            return await GetAsync<ActiveQuestsResponse>("/api/quests/active");
        }

        /// <summary>
        /// Abandon an active quest.
        /// </summary>
        public async Task<QuestActionResponse> AbandonQuestAsync(string questId)
        {
            return await PostAsync<QuestActionResponse>($"/api/quests/{questId}/abandon", null);
        }
        
        /// <summary>
        /// Export all player data for game save.
        /// </summary>
        public async Task<PlayerExportData> ExportPlayerDataAsync(string playerId = null)
        {
            playerId = playerId ?? defaultPlayerId;
            return await PostAsync<PlayerExportData>($"/api/export/{playerId}", null);
        }
        
        /// <summary>
        /// Import player data from game save.
        /// </summary>
        public async Task ImportPlayerDataAsync(PlayerExportData data)
        {
            await PostAsync<ImportResponse>("/api/import", data);
        }
        
        #endregion
        
        #region Private Methods
        
        private IEnumerator GenerateResponseStreamCoroutine(
            string npcName,
            string playerInput,
            Action<string> onToken,
            Action<string> onComplete,
            string playerId,
            Dictionary<string, object> gameState)
        {
            var request = new GenerateRequest
            {
                npc_name = npcName,
                player_input = playerInput,
                player_id = playerId ?? defaultPlayerId,
                game_state = gameState
            };
            
            var json = JsonUtility.ToJson(request);
            var url = $"{serverUrl}/api/dialogue/generate/stream";
            
            using (var webRequest = new UnityWebRequest(url, "POST"))
            {
                webRequest.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
                webRequest.downloadHandler = new DownloadHandlerBuffer();
                webRequest.SetRequestHeader("Content-Type", "application/json");
                webRequest.timeout = (int)requestTimeout;
                
                var operation = webRequest.SendWebRequest();
                
                StringBuilder fullResponse = new StringBuilder();
                
                while (!operation.isDone)
                {
                    // Check for new data
                    var downloadedData = webRequest.downloadHandler.text;
                    
                    // Parse SSE events
                    var lines = downloadedData.Split('\n');
                    foreach (var line in lines)
                    {
                        if (line.StartsWith("data: "))
                        {
                            var json_data = line.Substring(6);
                            try
                            {
                                var eventData = JsonUtility.FromJson<StreamEventData>(json_data);
                                
                                if (!string.IsNullOrEmpty(eventData.token))
                                {
                                    fullResponse.Append(eventData.token);
                                    onToken?.Invoke(eventData.token);
                                    OnTokenReceived?.Invoke(eventData.token);
                                }
                                
                                if (eventData.done)
                                {
                                    onComplete?.Invoke(eventData.full_response ?? fullResponse.ToString());
                                    OnResponseReceived?.Invoke(fullResponse.ToString());
                                }
                            }
                            catch
                            {
                                // Skip malformed JSON
                            }
                        }
                    }
                    
                    yield return null;
                }
                
                if (webRequest.result == UnityWebRequest.Result.ConnectionError ||
                    webRequest.result == UnityWebRequest.Result.ProtocolError)
                {
                    OnError?.Invoke($"Streaming failed: {webRequest.error}");
                }
            }
        }
        
        private async Task<T> GetAsync<T>(string endpoint)
        {
            var url = $"{serverUrl}{endpoint}";
            
            using (var request = UnityWebRequest.Get(url))
            {
                request.timeout = (int)requestTimeout;
                request.SetRequestHeader("Accept", "application/json");
                
                var operation = request.SendWebRequest();
                
                while (!operation.isDone)
                {
                    await Task.Yield();
                }
                
                if (request.result == UnityWebRequest.Result.ConnectionError ||
                    request.result == UnityWebRequest.Result.ProtocolError)
                {
                    throw new Exception($"GET {endpoint} failed: {request.error}");
                }
                
                var json = request.downloadHandler.text;
                LogDebug($"GET {endpoint}: {json}");
                return JsonUtility.FromJson<T>(json);
            }
        }
        
        private async Task<T> PostAsync<T>(string endpoint, object data)
        {
            var url = $"{serverUrl}{endpoint}";
            var json = data != null ? JsonUtility.ToJson(data) : "{}";
            
            using (var request = new UnityWebRequest(url, "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.timeout = (int)requestTimeout;
                
                var operation = request.SendWebRequest();
                
                while (!operation.isDone)
                {
                    await Task.Yield();
                }
                
                if (request.result == UnityWebRequest.Result.ConnectionError ||
                    request.result == UnityWebRequest.Result.ProtocolError)
                {
                    throw new Exception($"POST {endpoint} failed: {request.error}");
                }
                
                var responseJson = request.downloadHandler.text;
                LogDebug($"POST {endpoint}: {responseJson}");
                return JsonUtility.FromJson<T>(responseJson);
            }
        }
        
        private async Task DeleteAsync(string endpoint)
        {
            var url = $"{serverUrl}{endpoint}";
            
            using (var request = UnityWebRequest.Delete(url))
            {
                request.timeout = (int)requestTimeout;
                
                var operation = request.SendWebRequest();
                
                while (!operation.isDone)
                {
                    await Task.Yield();
                }
                
                if (request.result == UnityWebRequest.Result.ConnectionError ||
                    request.result == UnityWebRequest.Result.ProtocolError)
                {
                    throw new Exception($"DELETE {endpoint} failed: {request.error}");
                }
            }
        }
        
        private void LogDebug(string message)
        {
            if (debugLogging)
                Debug.Log($"[NPCDialogue] {message}");
        }
        
        #endregion
        
        #region Unity Lifecycle
        
        private void Start()
        {
            // Start connection check
            _connectionCheckCoroutine = StartCoroutine(ConnectionCheckLoop());
        }
        
        private void OnDestroy()
        {
            if (_connectionCheckCoroutine != null)
            {
                StopCoroutine(_connectionCheckCoroutine);
            }
        }
        
        private IEnumerator ConnectionCheckLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(5f);
                _ = CheckConnectionAsync();
            }
        }
        
        #endregion
    }
    
    #region Data Classes
    
    [Serializable]
    public class StatusResponse
    {
        public string status;
        public string version;
        public List<string> loaded_npcs;
        public string model;
        public bool ollama_connected;
    }
    
    [Serializable]
    public class GenerateRequest
    {
        public string npc_name;
        public string player_input;
        public string player_id;
        public Dictionary<string, object> game_state;
    }
    
    [Serializable]
    public class DialogueResponse
    {
        public string response;
        public string npc_name;
        public int tokens;
        public float elapsed_time;
        public float tokens_per_second;
    }
    
    [Serializable]
    public class LoadCharacterRequest
    {
        public string character_path;
        public string player_id;
    }
    
    [Serializable]
    public class CharacterLoadResponse
    {
        public string status;
        public string character_name;
        public string description;
    }
    
    [Serializable]
    public class CharacterInfo
    {
        public string name;
        public string description;
        public string personality;
        public string speaking_style;
    }
    
    [Serializable]
    public class CharacterListResponse
    {
        public List<string> loaded;
        public List<AvailableCharacter> available;
    }
    
    [Serializable]
    public class AvailableCharacter
    {
        public string name;
        public string file;
        public string description;
    }
    
    [Serializable]
    public class UpdateRelationshipRequest
    {
        public string npc_name;
        public string player_id;
        public int change;
        public string reason;
    }
    
    [Serializable]
    public class RelationshipInfo
    {
        public string npc_name;
        public string player_id;
        public int score;
        public string level;
        public int history_count;
    }
    
    [Serializable]
    public class RelationshipUpdateResponse
    {
        public string status;
        public string npc_name;
        public string player_id;
        public int new_score;
        public string level;
    }
    
    [Serializable]
    public class RelationshipData
    {
        public int score;
        public string level;
    }
    
    [Serializable]
    public class SaveHistoryRequest
    {
        public string npc_name;
        public string player_id;
        public string directory;
    }
    
    [Serializable]
    public class LoadHistoryRequest
    {
        public string npc_name;
        public string player_id;
        public string directory;
    }
    
    [Serializable]
    public class SaveHistoryResponse
    {
        public string status;
        public string npc_name;
        public string player_id;
        public int turns;
    }
    
    [Serializable]
    public class LoadHistoryResponse
    {
        public string status;
        public string npc_name;
        public string player_id;
        public int turns;
    }
    
    [Serializable]
    public class GameState
    {
        public string location;
        public string timeOfDay;
        public string currentQuest;
        public int? playerHealth;
        public int? playerGold;
    }
    
    [Serializable]
    public class SaveAllResponse
    {
        public string status;
        public string message;
    }
    
    [Serializable]
    public class PlayerExportData
    {
        public string player_id;
        public Dictionary<string, RelationshipData> relationships;
        public string exported_at;
    }
    
    [Serializable]
    public class ImportResponse
    {
        public string status;
        public string player_id;
    }
    
    [Serializable]
    public class StreamEventData
    {
        public string token;
        public bool done;
        public string full_response;
        public string error;
    }

    // Quest System Data Classes

    [Serializable]
    public class GameEventRequest
    {
        public string event_type;
        public string target;
        public int amount = 1;
        public string location;
        public string player_id;
    }

    [Serializable]
    public class GameEventResponse
    {
        public string status;
        public string event_type;
        public string target;
        public int amount;
        public int quests_updated;
        public Dictionary<string, string> progress_updates;
        public List<QuestCompletionInfo> quests_ready_to_complete;
    }

    [Serializable]
    public class QuestCompletionInfo
    {
        public string quest_id;
        public string name;
        public Dictionary<string, object> rewards;
    }

    [Serializable]
    public class QuestListResponse
    {
        public string npc_name;
        public List<Dictionary<string, object>> quests;
    }

    [Serializable]
    public class QuestActionResponse
    {
        public string status;
        public Dictionary<string, object> quest;
    }

    [Serializable]
    public class QuestCompleteResponse
    {
        public string status;
        public string quest_id;
        public Dictionary<string, object> rewards;
    }

    [Serializable]
    public class ActiveQuestsResponse
    {
        public int count;
        public List<Dictionary<string, object>> quests;
    }

    #endregion
}
