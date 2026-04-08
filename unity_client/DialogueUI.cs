// Dialogue UI for Unity
// UI system for displaying NPC dialogue

using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace NPCDialogue
{
    /// <summary>
    /// UI system for displaying NPC dialogue.
    /// Attach to a Canvas or UI panel.
    /// </summary>
    public class DialogueUI : MonoBehaviour
    {
        [Header("UI References")]
        [Tooltip("Panel containing the dialogue UI")]
        public GameObject dialoguePanel;
        
        [Tooltip("Text element for NPC name")]
        public TMP_Text npcNameText;
        
        [Tooltip("Text element for dialogue content")]
        public TMP_Text dialogueText;
        
        [Tooltip("Input field for player input")]
        public TMP_InputField playerInputField;
        
        [Tooltip("Send button")]
        public Button sendButton;
        
        [Tooltip("Close button")]
        public Button closeButton;
        
        [Header("Visual Effects")]
        [Tooltip("Typing speed (seconds per character)")]
        public float typingSpeed = 0.02f;
        
        [Tooltip("Enable typewriter effect")]
        public bool useTypewriter = true;
        
        [Tooltip("Show thinking indicator")]
        public GameObject thinkingIndicator;
        
        [Header("Relationship Display")]
        [Tooltip("Show relationship indicator")]
        public bool showRelationship = true;
        
        [Tooltip("Relationship slider/bar")]
        public Slider relationshipSlider;
        
        [Tooltip("Relationship level text")]
        public TMP_Text relationshipLevelText;
        
        [Header("Animation")]
        [Tooltip("Animator for panel animations")]
        public Animator panelAnimator;
        
        [Tooltip("Animation trigger to show")]
        public string showTrigger = "Show";
        
        [Tooltip("Animation trigger to hide")]
        public string hideTrigger = "Hide";
        
        // Events
        public event Action OnDialogueClosed;
        public event Action<string> OnMessageSent;
        
        // State
        private NPCCharacter _currentNPC;
        private bool _isTyping = false;
        private Coroutine _typewriterCoroutine;
        private StringBuilder _currentText = new StringBuilder();
        
        #region Public API
        
        /// <summary>
        /// Show the dialogue UI for an NPC.
        /// </summary>
        public void Show(string npcName, NPCCharacter npc)
        {
            _currentNPC = npc;
            
            // Set NPC name
            if (npcNameText != null)
            {
                npcNameText.text = npcName;
            }
            
            // Clear previous dialogue
            ClearDialogue();
            
            // Show panel
            if (dialoguePanel != null)
            {
                dialoguePanel.SetActive(true);
            }
            
            // Trigger animation
            if (panelAnimator != null)
            {
                panelAnimator.SetTrigger(showTrigger);
            }
            
            // Subscribe to relationship changes
            if (showRelationship && _currentNPC != null)
            {
                _currentNPC.OnRelationshipChanged += UpdateRelationshipDisplay;
            }
            
            // Focus input field
            if (playerInputField != null)
            {
                playerInputField.Select();
                playerInputField.ActivateInputField();
            }
        }
        
        /// <summary>
        /// Hide the dialogue UI.
        /// </summary>
        public void Hide()
        {
            // Unsubscribe
            if (_currentNPC != null)
            {
                _currentNPC.OnRelationshipChanged -= UpdateRelationshipDisplay;
            }
            
            // Trigger animation
            if (panelAnimator != null)
            {
                panelAnimator.SetTrigger(hideTrigger);
            }
            else if (dialoguePanel != null)
            {
                dialoguePanel.SetActive(false);
            }
            
            _currentNPC = null;
            OnDialogueClosed?.Invoke();
        }
        
        /// <summary>
        /// Show a response from the NPC.
        /// </summary>
        public void ShowResponse(string npcName, string response)
        {
            if (dialogueText != null)
            {
                if (useTypewriter)
                {
                    StartTypewriter(response);
                }
                else
                {
                    dialogueText.text = response;
                }
            }
            
            // Hide thinking indicator
            HideThinking();
        }
        
        /// <summary>
        /// Show speaker name.
        /// </summary>
        public void ShowSpeakerName(string name)
        {
            if (npcNameText != null)
            {
                npcNameText.text = name;
            }
        }
        
        /// <summary>
        /// Append a token to the current dialogue (for streaming).
        /// </summary>
        public void AppendToken(string token)
        {
            _currentText.Append(token);
            
            if (dialogueText != null)
            {
                dialogueText.text = _currentText.ToString();
            }
        }
        
        /// <summary>
        /// Clear the dialogue text.
        /// </summary>
        public void ClearDialogue()
        {
            _currentText.Clear();
            
            if (dialogueText != null)
            {
                dialogueText.text = "";
            }
            
            if (playerInputField != null)
            {
                playerInputField.text = "";
            }
        }
        
        /// <summary>
        /// Show thinking indicator.
        /// </summary>
        public void ShowThinking(string npcName)
        {
            if (thinkingIndicator != null)
            {
                thinkingIndicator.SetActive(true);
            }
            
            if (dialogueText != null)
            {
                dialogueText.text = "...";
            }
        }
        
        /// <summary>
        /// Hide thinking indicator.
        /// </summary>
        public void HideThinking()
        {
            if (thinkingIndicator != null)
            {
                thinkingIndicator.SetActive(false);
            }
        }
        
        /// <summary>
        /// Show an error message.
        /// </summary>
        public void ShowError(string message)
        {
            HideThinking();
            
            if (dialogueText != null)
            {
                dialogueText.text = $"<color=red>[Error] {message}</color>";
            }
        }
        
        /// <summary>
        /// Update relationship display.
        /// </summary>
        public void UpdateRelationshipDisplay(int score, string level)
        {
            if (relationshipSlider != null)
            {
                // Map -100 to 100 to 0 to 1
                relationshipSlider.value = (score + 100) / 200f;
            }
            
            if (relationshipLevelText != null)
            {
                relationshipLevelText.text = $"{level} ({score:+#;-#;0})";
            }
        }
        
        #endregion
        
        #region Unity Lifecycle
        
        private void Start()
        {
            // Setup button listeners
            if (sendButton != null)
            {
                sendButton.onClick.AddListener(OnSendButtonClicked);
            }
            
            if (closeButton != null)
            {
                closeButton.onClick.AddListener(OnCloseButtonClicked);
            }
            
            // Setup input field
            if (playerInputField != null)
            {
                playerInputField.onSubmit.AddListener(OnInputSubmit);
            }
            
            // Hide by default
            if (dialoguePanel != null)
            {
                dialoguePanel.SetActive(false);
            }
        }
        
        private void OnDestroy()
        {
            if (sendButton != null)
            {
                sendButton.onClick.RemoveListener(OnSendButtonClicked);
            }
            
            if (closeButton != null)
            {
                closeButton.onClick.RemoveListener(OnCloseButtonClicked);
            }
            
            if (playerInputField != null)
            {
                playerInputField.onSubmit.RemoveListener(OnInputSubmit);
            }
        }
        
        #endregion
        
        #region Private Methods
        
        private void StartTypewriter(string text)
        {
            if (_typewriterCoroutine != null)
            {
                StopCoroutine(_typewriterCoroutine);
            }
            
            _typewriterCoroutine = StartCoroutine(TypewriterEffect(text));
        }
        
        private IEnumerator TypewriterEffect(string text)
        {
            _isTyping = true;
            _currentText.Clear();
            
            foreach (char c in text)
            {
                _currentText.Append(c);
                
                if (dialogueText != null)
                {
                    dialogueText.text = _currentText.ToString();
                }
                
                yield return new WaitForSeconds(typingSpeed);
            }
            
            _isTyping = false;
        }
        
        private void OnSendButtonClicked()
        {
            SendCurrentMessage();
        }
        
        private void OnCloseButtonClicked()
        {
            Hide();
        }
        
        private void OnInputSubmit(string text)
        {
            SendCurrentMessage();
        }
        
        private void SendCurrentMessage()
        {
            if (playerInputField == null || string.IsNullOrWhiteSpace(playerInputField.text))
                return;
            
            string message = playerInputField.text.Trim();
            playerInputField.text = "";
            
            // Send to NPC
            if (_currentNPC != null)
            {
                // Show player message in dialogue
                AppendToken($"\n<color=#88ff88>Player:</color> {message}\n\n");
                
                // Send to NPC (use streaming for better UX)
                _currentNPC.SendMessageStream(message);
            }
            
            // Fire event
            OnMessageSent?.Invoke(message);
            
            // Re-focus input
            playerInputField.Select();
            playerInputField.ActivateInputField();
        }
        
        #endregion
    }
}
