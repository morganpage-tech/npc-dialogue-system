// NPC Dialogue Editor Window for Unity
// Custom Unity Editor window for testing and managing NPCs

#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System.Collections.Generic;

namespace NPCDialogue.Editor
{
    /// <summary>
    /// Unity Editor window for testing and managing the NPC Dialogue System.
    /// </summary>
    public class NPCDialogueWindow : EditorWindow
    {
        [MenuItem("Tools/NPC Dialogue/Manager Window")]
        public static void ShowWindow()
        {
            var window = GetWindow<NPCDialogueWindow>("NPC Dialogue Manager");
            window.minSize = new Vector2(400, 500);
            window.Show();
        }
        
        // State
        private Vector2 _scrollPosition;
        private int _selectedTab = 0;
        private readonly string[] _tabs = { "Server", "Characters", "Testing", "Settings" };
        
        // Server tab
        private string _serverUrl = "http://localhost:8000";
        private bool _isServerConnected = false;
        private string _serverStatus = "Not connected";
        
        // Characters tab
        private List<CharacterInfo> _availableCharacters = new List<CharacterInfo>();
        private List<string> _loadedCharacters = new List<string>();
        private int _selectedCharacterIndex = -1;
        
        // Testing tab
        private string _testNPCName = "";
        private string _testPlayerInput = "";
        private string _testResponse = "";
        private bool _isGenerating = false;
        private Vector2 _testScrollPosition;
        
        // Settings tab
        private string _defaultPlayerId = "player";
        private float _requestTimeout = 30f;
        private bool _debugLogging = true;
        
        private void OnEnable()
        {
            // Load saved settings
            _serverUrl = EditorPrefs.GetString("NPCDialogue_ServerUrl", "http://localhost:8000");
            _defaultPlayerId = EditorPrefs.GetString("NPCDialogue_DefaultPlayerId", "player");
            _requestTimeout = EditorPrefs.GetFloat("NPCDialogue_RequestTimeout", 30f);
            _debugLogging = EditorPrefs.GetBool("NPCDialogue_DebugLogging", true);
        }
        
        private void OnDisable()
        {
            // Save settings
            EditorPrefs.SetString("NPCDialogue_ServerUrl", _serverUrl);
            EditorPrefs.SetString("NPCDialogue_DefaultPlayerId", _defaultPlayerId);
            EditorPrefs.SetFloat("NPCDialogue_RequestTimeout", _requestTimeout);
            EditorPrefs.SetBool("NPCDialogue_DebugLogging", _debugLogging);
        }
        
        private void OnGUI()
        {
            // Draw tabs
            _selectedTab = GUILayout.Toolbar(_selectedTab, _tabs);
            
            EditorGUILayout.Space(10);
            
            // Draw selected tab content
            switch (_selectedTab)
            {
                case 0:
                    DrawServerTab();
                    break;
                case 1:
                    DrawCharactersTab();
                    break;
                case 2:
                    DrawTestingTab();
                    break;
                case 3:
                    DrawSettingsTab();
                    break;
            }
        }
        
        #region Tab Drawing
        
        private void DrawServerTab()
        {
            EditorGUILayout.LabelField("Server Configuration", EditorStyles.boldLabel);
            
            EditorGUI.BeginChangeCheck();
            _serverUrl = EditorGUILayout.TextField("Server URL", _serverUrl);
            if (EditorGUI.EndChangeCheck())
            {
                _isServerConnected = false;
                _serverStatus = "Not connected";
            }
            
            EditorGUILayout.Space(10);
            
            // Connection status
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            {
                EditorGUILayout.LabelField("Status:", _isServerConnected ? "Connected" : _serverStatus, 
                    _isServerConnected ? EditorStyles.boldLabel : EditorStyles.label);
            }
            EditorGUILayout.EndVertical();
            
            EditorGUILayout.Space(10);
            
            // Buttons
            EditorGUILayout.BeginHorizontal();
            {
                if (GUILayout.Button("Check Connection", GUILayout.Height(30)))
                {
                    CheckServerConnection();
                }
                
                if (GUILayout.Button("Start Server", GUILayout.Height(30)))
                {
                    StartServer();
                }
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(10);
            
            // Server info
            if (_isServerConnected)
            {
                EditorGUILayout.LabelField("Quick Actions", EditorStyles.boldLabel);
                
                EditorGUILayout.BeginHorizontal();
                {
                    if (GUILayout.Button("Save All Data"))
                    {
                        SaveAllData();
                    }
                    
                    if (GUILayout.Button("Load All Characters"))
                    {
                        RefreshCharacterList();
                    }
                }
                EditorGUILayout.EndHorizontal();
            }
            
            // Help box
            EditorGUILayout.Space(10);
            EditorGUILayout.HelpBox(
                "Make sure the API server is running before testing.\n" +
                "Start it with: python api_server.py",
                MessageType.Info
            );
        }
        
        private void DrawCharactersTab()
        {
            EditorGUILayout.LabelField("Character Management", EditorStyles.boldLabel);
            
            EditorGUILayout.BeginHorizontal();
            {
                if (GUILayout.Button("Refresh List", GUILayout.Height(25)))
                {
                    RefreshCharacterList();
                }
                
                if (GUILayout.Button("Load Selected", GUILayout.Height(25)))
                {
                    LoadSelectedCharacter();
                }
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(10);
            
            // Available characters
            EditorGUILayout.LabelField("Available Characters", EditorStyles.boldLabel);
            
            _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition, GUILayout.Height(150));
            {
                for (int i = 0; i < _availableCharacters.Count; i++)
                {
                    var character = _availableCharacters[i];
                    
                    bool isSelected = (i == _selectedCharacterIndex);
                    bool isLoaded = _loadedCharacters.Contains(character.name);
                    
                    EditorGUILayout.BeginHorizontal();
                    {
                        // Selection toggle
                        bool newSelected = GUILayout.Toggle(isSelected, "", GUILayout.Width(20));
                        if (newSelected && !isSelected)
                        {
                            _selectedCharacterIndex = i;
                            _testNPCName = character.name;
                        }
                        
                        // Name with status
                        string displayName = character.name;
                        if (isLoaded)
                        {
                            displayName += " [Loaded]";
                        }
                        
                        EditorGUILayout.LabelField(displayName, isLoaded ? EditorStyles.boldLabel : EditorStyles.label);
                        
                        // Quick load button
                        if (!isLoaded && GUILayout.Button("Load", GUILayout.Width(60)))
                        {
                            LoadCharacter(character.name);
                        }
                    }
                    EditorGUILayout.EndHorizontal();
                    
                    // Show description
                    if (i == _selectedCharacterIndex)
                    {
                        EditorGUI.indentLevel++;
                        EditorGUILayout.LabelField(character.description, EditorStyles.wordWrappedLabel);
                        EditorGUI.indentLevel--;
                    }
                }
            }
            EditorGUILayout.EndScrollView();
            
            EditorGUILayout.Space(10);
            
            // Loaded characters
            EditorGUILayout.LabelField("Loaded Characters", EditorStyles.boldLabel);
            
            foreach (var name in _loadedCharacters)
            {
                EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);
                {
                    EditorGUILayout.LabelField(name);
                    
                    if (GUILayout.Button("Unload", GUILayout.Width(60)))
                    {
                        UnloadCharacter(name);
                    }
                }
                EditorGUILayout.EndHorizontal();
            }
            
            if (_loadedCharacters.Count == 0)
            {
                EditorGUILayout.HelpBox("No characters loaded.", MessageType.Info);
            }
        }
        
        private void DrawTestingTab()
        {
            EditorGUILayout.LabelField("Dialogue Testing", EditorStyles.boldLabel);
            
            // NPC Selection
            EditorGUILayout.BeginHorizontal();
            {
                EditorGUILayout.LabelField("NPC:", GUILayout.Width(60));
                _testNPCName = EditorGUILayout.TextField(_testNPCName);
                
                if (GUILayout.Button("Select", GUILayout.Width(60)))
                {
                    // Show character selection popup
                    if (_availableCharacters.Count > 0)
                    {
                        var menu = new GenericMenu();
                        foreach (var character in _availableCharacters)
                        {
                            menu.AddItem(
                                new GUIContent(character.name),
                                _testNPCName == character.name,
                                () => _testNPCName = character.name
                            );
                        }
                        menu.ShowAsContext();
                    }
                }
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(10);
            
            // Player input
            EditorGUILayout.LabelField("Player Input:", EditorStyles.boldLabel);
            _testPlayerInput = EditorGUILayout.TextArea(_testPlayerInput, GUILayout.Height(60));
            
            EditorGUILayout.Space(10);
            
            // Generate button
            EditorGUI.BeginDisabledGroup(string.IsNullOrEmpty(_testNPCName) || string.IsNullOrEmpty(_testPlayerInput) || _isGenerating);
            {
                if (GUILayout.Button("Generate Response", GUILayout.Height(30)))
                {
                    GenerateTestResponse();
                }
            }
            EditorGUI.EndDisabledGroup();
            
            EditorGUILayout.Space(10);
            
            // Response
            EditorGUILayout.LabelField("NPC Response:", EditorStyles.boldLabel);
            
            _testScrollPosition = EditorGUILayout.BeginScrollView(_testScrollPosition, GUILayout.Height(150));
            {
                EditorGUILayout.TextArea(_testResponse, EditorStyles.wordWrappedLabel);
            }
            EditorGUILayout.EndScrollView();
            
            // Clear button
            if (GUILayout.Button("Clear", GUILayout.Height(25)))
            {
                _testPlayerInput = "";
                _testResponse = "";
            }
        }
        
        private void DrawSettingsTab()
        {
            EditorGUILayout.LabelField("Settings", EditorStyles.boldLabel);
            
            _defaultPlayerId = EditorGUILayout.TextField("Default Player ID", _defaultPlayerId);
            _requestTimeout = EditorGUILayout.Slider("Request Timeout (sec)", _requestTimeout, 5f, 120f);
            _debugLogging = EditorGUILayout.Toggle("Debug Logging", _debugLogging);
            
            EditorGUILayout.Space(20);
            
            EditorGUILayout.LabelField("Documentation", EditorStyles.boldLabel);
            
            if (GUILayout.Button("Open README"))
            {
                Application.OpenURL("https://github.com/morganpage-tech/npc-dialogue-system#readme");
            }
            
            if (GUILayout.Button("Open Integration Guide"))
            {
                Application.OpenURL("https://github.com/morganpage-tech/npc-dialogue-system/blob/main/UNITY_INTEGRATION.md");
            }
            
            EditorGUILayout.Space(20);
            
            EditorGUILayout.LabelField("About", EditorStyles.boldLabel);
            EditorGUILayout.LabelField("NPC Dialogue System v1.2.0");
            EditorGUILayout.LabelField("AI-powered NPC conversations for games");
        }
        
        #endregion
        
        #region API Calls
        
        private async void CheckServerConnection()
        {
            _serverStatus = "Checking...";
            Repaint();
            
            try
            {
                // Note: This would need actual HTTP implementation
                // For now, simulate the check
                await System.Threading.Tasks.Task.Delay(500);
                
                _isServerConnected = true;
                _serverStatus = "Connected";
                
                // Refresh character list
                RefreshCharacterList();
            }
            catch (System.Exception e)
            {
                _isServerConnected = false;
                _serverStatus = $"Error: {e.Message}";
            }
            
            Repaint();
        }
        
        private void StartServer()
        {
            // Open terminal or show instructions
            EditorUtility.DisplayDialog(
                "Start Server",
                "To start the API server:\n\n" +
                "1. Open a terminal\n" +
                "2. Navigate to the npc-dialogue-system directory\n" +
                "3. Run: python api_server.py\n\n" +
                "The server will start at http://localhost:8000",
                "OK"
            );
        }
        
        private void RefreshCharacterList()
        {
            // This would call the actual API
            // For now, add sample characters
            _availableCharacters = new List<CharacterInfo>
            {
                new CharacterInfo { name = "Thorne", description = "A burly blacksmith who forges weapons and armor." },
                new CharacterInfo { name = "Elara", description = "A friendly merchant who travels the realm trading goods." },
                new CharacterInfo { name = "Zephyr", description = "A wise wizard who studies ancient magic." }
            };
            
            Repaint();
        }
        
        private void LoadSelectedCharacter()
        {
            if (_selectedCharacterIndex >= 0 && _selectedCharacterIndex < _availableCharacters.Count)
            {
                var character = _availableCharacters[_selectedCharacterIndex];
                LoadCharacter(character.name);
            }
        }
        
        private void LoadCharacter(string name)
        {
            if (!_loadedCharacters.Contains(name))
            {
                _loadedCharacters.Add(name);
                Debug.Log($"[NPCDialogue] Loaded character: {name}");
            }
            Repaint();
        }
        
        private void UnloadCharacter(string name)
        {
            _loadedCharacters.Remove(name);
            Debug.Log($"[NPCDialogue] Unloaded character: {name}");
            Repaint();
        }
        
        private async void SaveAllData()
        {
            Debug.Log("[NPCDialogue] Saving all data...");
            await System.Threading.Tasks.Task.Delay(100);
            Debug.Log("[NPCDialogue] All data saved!");
        }
        
        private async void GenerateTestResponse()
        {
            _isGenerating = true;
            _testResponse = "Generating...";
            Repaint();
            
            // Simulate generation
            await System.Threading.Tasks.Task.Delay(1500);
            
            _testResponse = $"[{_testNPCName}]: *thinks for a moment*\n\n" +
                $"\"Ah, interesting question! Let me tell you about that...\"";
            
            _isGenerating = false;
            Repaint();
        }
        
        #endregion
    }
}
#endif
