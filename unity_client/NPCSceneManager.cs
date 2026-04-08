// NPC Manager for Unity
// Manages all NPCs in the scene

using System;
using System.Collections.Generic;
using UnityEngine;

namespace NPCDialogue
{
    /// <summary>
    /// Manages all NPCs in the scene. Handles loading, saving, and global operations.
    /// </summary>
    public class NPCSceneManager : MonoBehaviour
    {
        public static NPCSceneManager Instance { get; private set; }
        
        [Header("Configuration")]
        [Tooltip("Default player ID")]
        public string defaultPlayerId = "player";
        
        [Tooltip("Auto-load all NPCs on start")]
        public bool autoLoadOnStart = true;
        
        [Tooltip("Auto-save interval in seconds (0 = disabled)")]
        public float autoSaveInterval = 60f;
        
        [Header("References")]
        [Tooltip("Dialogue UI reference")]
        public DialogueUI dialogueUI;
        
        // State
        private Dictionary<string, NPCCharacter> _npcs = new Dictionary<string, NPCCharacter>();
        private NPCDialogueClient _client;
        private float _lastSaveTime;
        
        // Events
        public event Action<string> OnNPCLoaded;
        public event Action<string> OnNPCUnloaded;
        public event Action OnAllSaved;
        
        #region Public API
        
        /// <summary>
        /// Get an NPC by name.
        /// </summary>
        public NPCCharacter GetNPC(string name)
        {
            if (_npcs.TryGetValue(name, out var npc))
            {
                return npc;
            }
            return null;
        }
        
        /// <summary>
        /// Get all NPCs.
        /// </summary>
        public IEnumerable<NPCCharacter> GetAllNPCs()
        {
            return _npcs.Values;
        }
        
        /// <summary>
        /// Register an NPC with the manager.
        /// </summary>
        public void RegisterNPC(NPCCharacter npc)
        {
            if (string.IsNullOrEmpty(npc.characterName))
            {
                Debug.LogWarning("[NPCSceneManager] Cannot register NPC with empty name");
                return;
            }
            
            if (_npcs.ContainsKey(npc.characterName))
            {
                Debug.LogWarning($"[NPCSceneManager] NPC '{npc.characterName}' already registered");
                return;
            }
            
            _npcs[npc.characterName] = npc;
            OnNPCLoaded?.Invoke(npc.characterName);
            
            Debug.Log($"[NPCSceneManager] Registered NPC: {npc.characterName}");
        }
        
        /// <summary>
        /// Unregister an NPC from the manager.
        /// </summary>
        public void UnregisterNPC(string name)
        {
            if (_npcs.Remove(name))
            {
                OnNPCUnloaded?.Invoke(name);
                Debug.Log($"[NPCSceneManager] Unregistered NPC: {name}");
            }
        }
        
        /// <summary>
        /// Save all NPC conversation histories.
        /// </summary>
        public async void SaveAll()
        {
            if (_client == null) return;
            
            try
            {
                await _client.SaveAllAsync();
                _lastSaveTime = Time.time;
                OnAllSaved?.Invoke();
                Debug.Log("[NPCSceneManager] Saved all NPC data");
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCSceneManager] Failed to save: {e.Message}");
            }
        }
        
        /// <summary>
        /// Export all player data for save game.
        /// </summary>
        public async void ExportPlayerData(string playerId = null)
        {
            if (_client == null) return;
            
            playerId = playerId ?? defaultPlayerId;
            
            try
            {
                var data = await _client.ExportPlayerDataAsync(playerId);
                // Save to PlayerPrefs or file
                var json = JsonUtility.ToJson(data);
                PlayerPrefs.SetString($"NPCData_{playerId}", json);
                PlayerPrefs.Save();
                
                Debug.Log($"[NPCSceneManager] Exported player data for {playerId}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCSceneManager] Failed to export: {e.Message}");
            }
        }
        
        /// <summary>
        /// Import player data from save game.
        /// </summary>
        public async void ImportPlayerData(string playerId = null)
        {
            if (_client == null) return;
            
            playerId = playerId ?? defaultPlayerId;
            
            var json = PlayerPrefs.GetString($"NPCData_{playerId}", "");
            if (string.IsNullOrEmpty(json))
            {
                Debug.LogWarning($"[NPCSceneManager] No saved data for player {playerId}");
                return;
            }
            
            try
            {
                var data = JsonUtility.FromJson<PlayerExportData>(json);
                await _client.ImportPlayerDataAsync(data);
                
                // Refresh all NPC relationships
                foreach (var npc in _npcs.Values)
                {
                    npc.RefreshRelationship();
                }
                
                Debug.Log($"[NPCSceneManager] Imported player data for {playerId}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCSceneManager] Failed to import: {e.Message}");
            }
        }
        
        /// <summary>
        /// Get relationship summary for all NPCs.
        /// </summary>
        public Dictionary<string, int> GetAllRelationships(string playerId = null)
        {
            playerId = playerId ?? defaultPlayerId;
            var relationships = new Dictionary<string, int>();
            
            foreach (var kvp in _npcs)
            {
                // Note: This would need to be async in real implementation
                // relationships[kvp.Key] = kvp.Value.GetCurrentRelationship();
            }
            
            return relationships;
        }
        
        #endregion
        
        #region Unity Lifecycle
        
        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }
        
        private void Start()
        {
            // Find client
            _client = FindObjectOfType<NPCDialogueClient>();
            
            if (_client == null)
            {
                Debug.LogError("[NPCSceneManager] No NPCDialogueClient found!");
                return;
            }
            
            // Find all NPCs in scene
            if (autoLoadOnStart)
            {
                var allNPCs = FindObjectsOfType<NPCCharacter>();
                foreach (var npc in allNPCs)
                {
                    RegisterNPC(npc);
                }
            }
            
            // Find dialogue UI
            if (dialogueUI == null)
            {
                dialogueUI = FindObjectOfType<DialogueUI>();
            }
        }
        
        private void Update()
        {
            // Auto-save
            if (autoSaveInterval > 0 && Time.time - _lastSaveTime >= autoSaveInterval)
            {
                SaveAll();
            }
        }
        
        private void OnApplicationPause(bool pauseStatus)
        {
            if (pauseStatus)
            {
                SaveAll();
            }
        }
        
        private void OnApplicationQuit()
        {
            SaveAll();
        }
        
        #endregion
    }
}
