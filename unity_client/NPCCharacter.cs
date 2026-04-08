// NPC Character Component for Unity
// Attach this to NPCs in your game world

using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace NPCDialogue
{
    /// <summary>
    /// Attach this component to NPC GameObjects in your scene.
    /// Manages dialogue interaction and visual feedback.
    /// </summary>
    public class NPCCharacter : MonoBehaviour, IInteractable
    {
        [Header("Character Configuration")]
        [Tooltip("Name of the character (must match character card)")]
        public string characterName;
        
        [Tooltip("Path to character card JSON file")]
        public string characterCardPath;
        
        [Tooltip("Player ID for this NPC")]
        public string playerId = "player";
        
        [Header("Interaction Settings")]
        [Tooltip("Maximum distance player can interact from")]
        public float interactionDistance = 3f;
        
        [Tooltip("Key to press to interact")]
        public KeyCode interactionKey = KeyCode.E;
        
        [Tooltip("Show interaction prompt")]
        public bool showPrompt = true;
        
        [Tooltip("Prompt text when player is in range")]
        public string promptText = "Press E to talk";
        
        [Header("Visual Feedback")]
        [Tooltip("Highlight color when player is in range")]
        public Color highlightColor = Color.yellow;
        
        [Tooltip("Reference to dialogue UI")]
        public DialogueUI dialogueUI;
        
        [Header("Audio (Optional)")]
        [Tooltip("Sound to play when NPC starts speaking")]
        public AudioClip onSpeakStart;
        
        [Tooltip("Sound to play when NPC stops speaking")]
        public AudioClip onSpeakEnd;
        
        // Events
        public event Action OnInteractionStart;
        public event Action OnInteractionEnd;
        public event Action<string> OnResponseReceived;
        public event Action<int, string> OnRelationshipChanged;
        
        // State
        private NPCDialogueClient _client;
        private CharacterInfo _characterInfo;
        private bool _isLoaded = false;
        private bool _isGenerating = false;
        private int _currentRelationship = 0;
        private string _currentRelationshipLevel = "Neutral";
        
        // Components
        private Renderer _renderer;
        private Color _originalColor;
        private Transform _playerTransform;
        private AudioSource _audioSource;
        
        // Conversation state
        private List<string> _conversationHistory = new List<string>();
        
        #region Unity Lifecycle
        
        private void Awake()
        {
            _renderer = GetComponent<Renderer>();
            if (_renderer != null)
            {
                _originalColor = _renderer.material.color;
            }
            
            _audioSource = GetComponent<AudioSource>();
            if (_audioSource == null && (onSpeakStart != null || onSpeakEnd != null))
            {
                _audioSource = gameObject.AddComponent<AudioSource>();
            }
            
            // Find or create dialogue UI
            if (dialogueUI == null)
            {
                dialogueUI = FindObjectOfType<DialogueUI>();
            }
        }
        
        private void Start()
        {
            // Find client
            _client = FindObjectOfType<NPCDialogueClient>();
            if (_client == null)
            {
                Debug.LogError($"[NPCCharacter] No NPCDialogueClient found in scene!");
                return;
            }
            
            // Subscribe to client events
            _client.OnError += OnClientError;
            
            // Load character
            LoadCharacter();
        }
        
        private void Update()
        {
            if (showPrompt && IsPlayerInRange())
            {
                // Show interaction prompt
                // (Implementation depends on your UI system)
            }
            
            // Check for interaction key
            if (IsPlayerInRange() && Input.GetKeyDown(interactionKey))
            {
                Interact();
            }
        }
        
        private void OnDestroy()
        {
            if (_client != null)
            {
                _client.OnError -= OnClientError;
            }
        }
        
        #endregion
        
        #region Public API
        
        /// <summary>
        /// Send a message to this NPC and get a response.
        /// </summary>
        public async void SendMessage(string message, Dictionary<string, object> gameState = null)
        {
            if (_client == null || !_isLoaded)
            {
                Debug.LogWarning($"[NPCCharacter] Cannot send message - client not ready");
                return;
            }
            
            if (_isGenerating)
            {
                Debug.LogWarning($"[NPCCharacter] Already generating a response");
                return;
            }
            
            _isGenerating = true;
            
            // Add to history
            _conversationHistory.Add($"Player: {message}");
            
            // Show thinking indicator
            dialogueUI?.ShowThinking(characterName);
            
            try
            {
                var response = await _client.GenerateResponseAsync(
                    characterName,
                    message,
                    playerId,
                    gameState
                );
                
                // Add to history
                _conversationHistory.Add($"{characterName}: {response.response}");
                
                // Update UI
                dialogueUI?.ShowResponse(characterName, response.response);
                
                // Play audio
                PlayAudio(onSpeakEnd);
                
                // Fire event
                OnResponseReceived?.Invoke(response.response);
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCCharacter] Failed to get response: {e.Message}");
                dialogueUI?.ShowError("Failed to get response");
            }
            finally
            {
                _isGenerating = false;
            }
        }
        
        /// <summary>
        /// Send a message with streaming response.
        /// </summary>
        public void SendMessageStream(
            string message,
            Dictionary<string, object> gameState = null)
        {
            if (_client == null || !_isLoaded)
            {
                Debug.LogWarning($"[NPCCharacter] Cannot send message - client not ready");
                return;
            }
            
            if (_isGenerating)
            {
                Debug.LogWarning($"[NPCCharacter] Already generating a response");
                return;
            }
            
            _isGenerating = true;
            
            // Add to history
            _conversationHistory.Add($"Player: {message}");
            
            // Clear dialogue UI
            dialogueUI?.ClearDialogue();
            dialogueUI?.ShowSpeakerName(characterName);
            
            // Play audio
            PlayAudio(onSpeakStart);
            
            StringBuilder fullResponse = new StringBuilder();
            
            _client.GenerateResponseStream(
                characterName,
                message,
                onToken: (token) =>
                {
                    fullResponse.Append(token);
                    dialogueUI?.AppendToken(token);
                },
                onComplete: (response) =>
                {
                    _conversationHistory.Add($"{characterName}: {response}");
                    PlayAudio(onSpeakEnd);
                    OnResponseReceived?.Invoke(response);
                    _isGenerating = false;
                },
                playerId: playerId,
                gameState: gameState
            );
        }
        
        /// <summary>
        /// Update relationship with this NPC.
        /// </summary>
        public async void UpdateRelationship(int change, string reason = null)
        {
            if (_client == null) return;
            
            try
            {
                var response = await _client.UpdateRelationshipAsync(
                    characterName,
                    change,
                    reason,
                    playerId
                );
                
                _currentRelationship = response.new_score;
                _currentRelationshipLevel = response.level;
                
                OnRelationshipChanged?.Invoke(_currentRelationship, _currentRelationshipLevel);
                
                Debug.Log($"[NPCCharacter] Relationship with {characterName}: {_currentRelationship} ({_currentRelationshipLevel})");
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCCharacter] Failed to update relationship: {e.Message}");
            }
        }
        
        /// <summary>
        /// Get current relationship status.
        /// </summary>
        public async void RefreshRelationship()
        {
            if (_client == null) return;
            
            try
            {
                var info = await _client.GetRelationshipAsync(characterName, playerId);
                _currentRelationship = info.score;
                _currentRelationshipLevel = info.level;
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCCharacter] Failed to get relationship: {e.Message}");
            }
        }
        
        /// <summary>
        /// Load this character from the server.
        /// </summary>
        public async void LoadCharacter()
        {
            if (_client == null)
            {
                Debug.LogWarning($"[NPCCharacter] Client not ready, will retry...");
                Invoke(nameof(LoadCharacter), 1f);
                return;
            }
            
            try
            {
                _characterInfo = await _client.LoadCharacterAsync(
                    characterCardPath ?? $"{characterName.ToLower()}.json",
                    playerId
                );
                
                _isLoaded = true;
                Debug.Log($"[NPCCharacter] Loaded character: {characterName}");
                
                // Refresh relationship
                RefreshRelationship();
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCCharacter] Failed to load character: {e.Message}");
            }
        }
        
        /// <summary>
        /// Save conversation history.
        /// </summary>
        public async void SaveHistory()
        {
            if (_client == null || !_isLoaded) return;
            
            try
            {
                await _client.SaveHistoryAsync(characterName, playerId);
                Debug.Log($"[NPCCharacter] Saved conversation history for {characterName}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCCharacter] Failed to save history: {e.Message}");
            }
        }
        
        /// <summary>
        /// Load conversation history.
        /// </summary>
        public async void LoadHistory()
        {
            if (_client == null || !_isLoaded) return;
            
            try
            {
                var response = await _client.LoadHistoryAsync(characterName, playerId);
                Debug.Log($"[NPCCharacter] Loaded {response.turns} conversation turns for {characterName}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[NPCCharacter] Failed to load history: {e.Message}");
            }
        }
        
        /// <summary>
        /// Get conversation history.
        /// </summary>
        public List<string> GetConversationHistory()
        {
            return new List<string>(_conversationHistory);
        }
        
        /// <summary>
        /// Clear conversation history.
        /// </summary>
        public void ClearHistory()
        {
            _conversationHistory.Clear();
        }
        
        #endregion
        
        #region IInteractable
        
        public void Interact()
        {
            if (!_isLoaded)
            {
                Debug.LogWarning($"[NPCCharacter] {characterName} not loaded yet");
                return;
            }
            
            OnInteractionStart?.Invoke();
            
            // Show dialogue UI
            if (dialogueUI != null)
            {
                dialogueUI.Show(characterName, this);
            }
            
            // Send greeting if first interaction
            if (_conversationHistory.Count == 0)
            {
                SendMessage("Hello!");
            }
        }
        
        public bool CanInteract()
        {
            return _isLoaded && IsPlayerInRange();
        }
        
        public float GetInteractionDistance()
        {
            return interactionDistance;
        }
        
        #endregion
        
        #region Private Methods
        
        private bool IsPlayerInRange()
        {
            if (_playerTransform == null)
            {
                var player = GameObject.FindGameObjectWithTag("Player");
                if (player != null)
                {
                    _playerTransform = player.transform;
                }
            }
            
            if (_playerTransform == null) return false;
            
            float distance = Vector3.Distance(transform.position, _playerTransform.position);
            return distance <= interactionDistance;
        }
        
        private void PlayAudio(AudioClip clip)
        {
            if (_audioSource != null && clip != null)
            {
                _audioSource.PlayOneShot(clip);
            }
        }
        
        private void OnClientError(string error)
        {
            Debug.LogError($"[NPCCharacter] Client error: {error}");
        }
        
        #endregion
        
        #region Editor Visualization
        
        private void OnDrawGizmosSelected()
        {
            // Draw interaction range
            Gizmos.color = Color.cyan;
            Gizmos.DrawWireSphere(transform.position, interactionDistance);
        }
        
        #endregion
    }
    
    /// <summary>
    /// Interface for interactable objects.
    /// </summary>
    public interface IInteractable
    {
        void Interact();
        bool CanInteract();
        float GetInteractionDistance();
    }
}
