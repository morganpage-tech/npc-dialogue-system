// Relationship Tracker for Unity
// Client-side relationship tracking and display

using System;
using System.Collections.Generic;
using UnityEngine;

namespace NPCDialogue
{
    /// <summary>
    /// Client-side relationship tracking for UI display and caching.
    /// </summary>
    public class RelationshipTracker : MonoBehaviour
    {
        [Header("Settings")]
        [Tooltip("Enable relationship changes from dialogue")]
        public bool enableDialogueChanges = true;
        
        [Tooltip("Enable relationship changes from gifts")]
        public bool enableGiftChanges = true;
        
        [Tooltip("Enable relationship changes from quests")]
        public bool enableQuestChanges = true;
        
        // Events
        public event Action<string, int, string> OnRelationshipChanged;
        public event Action<string, int, int> OnRelationshipScoreChanged;
        
        // State
        private Dictionary<string, Dictionary<string, int>> _relationships = new Dictionary<string, Dictionary<string, int>>();
        private string _currentPlayerId = "player";
        
        // Relationship thresholds
        private static readonly Dictionary<string, (int min, int max)> RelationshipLevels = new Dictionary<string, (int, int)>
        {
            { "Hated", (-100, -50) },
            { "Disliked", (-50, -20) },
            { "Neutral", (-20, 20) },
            { "Liked", (20, 50) },
            { "Loved", (50, 80) },
            { "Adored", (80, 100) }
        };
        
        #region Public API
        
        /// <summary>
        /// Get relationship score for an NPC.
        /// </summary>
        public int GetScore(string npcName, string playerId = null)
        {
            playerId = playerId ?? _currentPlayerId;
            
            if (_relationships.TryGetValue(playerId, out var npcs))
            {
                if (npcs.TryGetValue(npcName, out var score))
                {
                    return score;
                }
            }
            
            return 0; // Neutral default
        }
        
        /// <summary>
        /// Set relationship score for an NPC.
        /// </summary>
        public void SetScore(string npcName, int score, string playerId = null)
        {
            playerId = playerId ?? _currentPlayerId;
            
            if (!_relationships.ContainsKey(playerId))
            {
                _relationships[playerId] = new Dictionary<string, int>();
            }
            
            var oldScore = GetScore(npcName, playerId);
            score = Mathf.Clamp(score, -100, 100);
            _relationships[playerId][npcName] = score;
            
            var level = GetLevelName(score);
            
            OnRelationshipScoreChanged?.Invoke(npcName, oldScore, score);
            OnRelationshipChanged?.Invoke(npcName, score, level);
        }
        
        /// <summary>
        /// Update relationship score by delta.
        /// </summary>
        public void UpdateScore(string npcName, int delta, string reason = null, string playerId = null)
        {
            var currentScore = GetScore(npcName, playerId);
            SetScore(npcName, currentScore + delta, playerId);
            
            Debug.Log($"[RelationshipTracker] {npcName}: {currentScore} -> {currentScore + delta} ({reason ?? "No reason"})");
        }
        
        /// <summary>
        /// Get relationship level name.
        /// </summary>
        public string GetLevelName(int score)
        {
            foreach (var level in RelationshipLevels)
            {
                if (score >= level.Value.min && score < level.Value.max)
                {
                    return level.Key;
                }
            }
            
            return "Neutral";
        }
        
        /// <summary>
        /// Get relationship level for an NPC.
        /// </summary>
        public string GetLevel(string npcName, string playerId = null)
        {
            return GetLevelName(GetScore(npcName, playerId));
        }
        
        /// <summary>
        /// Get color for relationship level.
        /// </summary>
        public Color GetLevelColor(int score)
        {
            if (score >= 80) return new Color(1f, 0.84f, 0f);      // Gold (Adored)
            if (score >= 50) return Color.green;                     // Loved
            if (score >= 20) return new Color(0.5f, 1f, 0.5f);      // Liked
            if (score >= -20) return Color.white;                    // Neutral
            if (score >= -50) return new Color(1f, 0.65f, 0f);      // Disliked
            return Color.red;                                         // Hated
        }
        
        /// <summary>
        /// Process dialogue and update relationship.
        /// </summary>
        public void ProcessDialogue(string npcName, string dialogueType, float sentiment = 0f, string playerId = null)
        {
            if (!enableDialogueChanges) return;
            
            int change = 0;
            
            switch (dialogueType.ToLower())
            {
                case "friendly":
                    change = 3;
                    break;
                case "flirt":
                    change = 5;
                    break;
                case "compliment":
                    change = 4;
                    break;
                case "neutral":
                    change = 0;
                    break;
                case "rude":
                    change = -5;
                    break;
                case "insult":
                    change = -10;
                    break;
                case "hostile":
                    change = -15;
                    break;
                default:
                    change = (int)(sentiment * 5);
                    break;
            }
            
            if (change != 0)
            {
                UpdateScore(npcName, change, $"Dialogue: {dialogueType}", playerId);
            }
        }
        
        /// <summary>
        /// Process gift and update relationship.
        /// </summary>
        public void ProcessGift(string npcName, string itemName, int itemValue, string playerId = null)
        {
            if (!enableGiftChanges) return;
            
            UpdateScore(npcName, itemValue, $"Gift: {itemName}", playerId);
        }
        
        /// <summary>
        /// Process quest completion and update relationship.
        /// </summary>
        public void ProcessQuest(string npcName, string questId, bool success, int reward = 15, string playerId = null)
        {
            if (!enableQuestChanges) return;
            
            int change = success ? reward : -reward;
            string reason = success ? $"Quest completed: {questId}" : $"Quest failed: {questId}";
            
            UpdateScore(npcName, change, reason, playerId);
        }
        
        /// <summary>
        /// Get all relationships for a player.
        /// </summary>
        public Dictionary<string, int> GetAllRelationships(string playerId = null)
        {
            playerId = playerId ?? _currentPlayerId;
            
            if (_relationships.TryGetValue(playerId, out var npcs))
            {
                return new Dictionary<string, int>(npcs);
            }
            
            return new Dictionary<string, int>();
        }
        
        /// <summary>
        /// Import relationships from saved data.
        /// </summary>
        public void ImportRelationships(Dictionary<string, int> data, string playerId = null)
        {
            playerId = playerId ?? _currentPlayerId;
            
            _relationships[playerId] = new Dictionary<string, int>(data);
        }
        
        /// <summary>
        /// Export relationships for saving.
        /// </summary>
        public Dictionary<string, int> ExportRelationships(string playerId = null)
        {
            return GetAllRelationships(playerId);
        }
        
        /// <summary>
        /// Reset all relationships for a player.
        /// </summary>
        public void ResetAllRelationships(string playerId = null)
        {
            playerId = playerId ?? _currentPlayerId;
            
            if (_relationships.ContainsKey(playerId))
            {
                _relationships[playerId].Clear();
            }
        }
        
        #endregion
        
        #region Static Helpers
        
        /// <summary>
        /// Get relationship level color (static helper).
        /// </summary>
        public static Color GetColorForScore(int score)
        {
            if (score >= 80) return new Color(1f, 0.84f, 0f);      // Gold
            if (score >= 50) return Color.green;
            if (score >= 20) return new Color(0.5f, 1f, 0.5f);
            if (score >= -20) return Color.white;
            if (score >= -50) return new Color(1f, 0.65f, 0f);
            return Color.red;
        }
        
        /// <summary>
        /// Get relationship level name (static helper).
        /// </summary>
        public static string GetLevelForScore(int score)
        {
            foreach (var level in RelationshipLevels)
            {
                if (score >= level.Value.min && score < level.Value.max)
                {
                    return level.Key;
                }
            }
            return "Neutral";
        }
        
        #endregion
    }
}
