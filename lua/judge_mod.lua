--[[
    MTG AI Judge Mod for Tabletop Simulator
    Works with "Oops I Baked a Pie" 4-player table

    Features:
    - Clickable Judge Mat for API key setup (no chat commands needed)
    - "judge <question>" chat command for rulings
    - "judge clear" to reset conversation session
    - Board state scraping (battlefield, graveyard, exile, hand)
    - Auto-spawns scripting zones — no manual GUID setup needed
    - Session-based conversation memory for follow-up questions
    - Broadcasts rulings to all players

    Setup:
    1. Paste this into Modding → Scripting → Global
    2. Save & Play — zones spawn automatically
    3. Type "judge zones" to see where zones are (colored boxes)
    4. If zones don't align with your table, adjust ZONE_POSITIONS below
    5. Click the Judge Mat to enter your API key
    6. Type "judge <question>" in chat
]]

---------------------------------------------------------------
-- CONFIGURATION
---------------------------------------------------------------

-- Server URL — update this after deployment
local SERVER_URL = "http://localhost:8080/judge"

-- Per-player API keys stored in memory (color -> key)
local PLAYER_KEYS = {}

-- Map player seat colors to player keys used in the API
-- Clockwise from White: White (bottom-right) → Red (bottom-left) → Yellow (top-left) → Blue (top-right)
local COLOR_TO_PLAYER = {
    White  = "player1",
    Red    = "player2",
    Yellow = "player3",
    Blue   = "player4",
}

-- Zone positions for "Oops I Baked a Pie" 4-player table
-- Each player has battlefield, graveyard, and exile zones
-- Adjust these {x, y, z} positions and {scaleX, scaleY, scaleZ} sizes to match your table layout
-- y=1 keeps zones just above the table surface
-- Type "judge zones" in chat to visualize where they are
local ZONE_POSITIONS = {
    -- White = bottom-right (white border), player 1, side column on RIGHT edge
    White = {
        battlefield = { position = {19, 2, 15}, scale = {46, 5, 30} },
        graveyard   = { position = {41, 2, 23}, scale = {8, 5, 6} },
        exile       = { position = {41, 2, 14}, scale = {8, 5, 6} },
    },
    -- Red = bottom-left (red border), player 2, side column on LEFT edge
    Red = {
        battlefield = { position = {-19, 2, 15}, scale = {46, 5, 30} },
        graveyard   = { position = {-41, 2, 23}, scale = {8, 5, 6} },
        exile       = { position = {-41, 2, 14}, scale = {8, 5, 6} },
    },
    -- Yellow = top-left (yellow border), player 3, side column on LEFT edge
    Yellow = {
        battlefield = { position = {-19, 2, -15}, scale = {46, 5, 30} },
        graveyard   = { position = {-41, 2, -23}, scale = {8, 5, 6} },
        exile       = { position = {-41, 2, -14}, scale = {8, 5, 6} },
    },
    -- Blue = top-right (blue border), player 4, side column on RIGHT edge
    Blue = {
        battlefield = { position = {19, 2, -15}, scale = {46, 5, 30} },
        graveyard   = { position = {41, 2, -23}, scale = {8, 5, 6} },
        exile       = { position = {41, 2, -14}, scale = {8, 5, 6} },
    },
}

-- Runtime zone object references (populated on load)
-- { White = { battlefield = zoneObj, graveyard = zoneObj, exile = zoneObj }, ... }
local ZONE_OBJECTS = {}

-- Visual marker objects for zones (so you can see them)
local ZONE_MARKERS = {}

-- Whether zone markers are currently visible
local showMarkers = true

-- Judge Mat object reference
local judgeMat = nil

---------------------------------------------------------------
-- GLOBAL UI (screen overlay for API key setup)
-- Uses Global UI.setXml so it renders as a reliable screen popup
---------------------------------------------------------------

local API_KEY_UI = [[
<Panel id="apiKeyPanel" active="false" height="220" width="450"
       position="0 0 0" showAnimation="FadeIn" hideAnimation="FadeOut"
       color="rgba(30,20,40,0.95)" outline="white" outlineSize="2">
  <VerticalLayout padding="20 20 20 20" spacing="10">
    <Text fontSize="28" color="#FFFFFF" alignment="MiddleCenter" fontStyle="Bold">MTG AI Judge</Text>
    <Text fontSize="16" color="#AAAAAA" alignment="MiddleCenter">Paste your Anthropic API Key below:</Text>
    <InputField id="apiKeyInput" fontSize="16" characterLimit="200"
                placeholder="sk-ant-..." color="#FFFFFF" textColor="#000000" />
    <HorizontalLayout spacing="10" preferredHeight="40">
      <Button id="saveKeyBtn" onClick="onSaveKey" fontSize="16"
              color="#4CAF50" textColor="#FFFFFF" preferredHeight="36">Save</Button>
      <Button id="cancelKeyBtn" onClick="onCancelKey" fontSize="16"
              color="#F44336" textColor="#FFFFFF" preferredHeight="36">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]]

function showApiKeyDialog()
    UI.setXml(API_KEY_UI)
    Wait.time(function()
        UI.setAttribute("apiKeyPanel", "active", "true")
    end, 0.3)
end

function hideApiKeyDialog()
    UI.setAttribute("apiKeyPanel", "active", "false")
end

---------------------------------------------------------------
-- SCRIPTING ZONE SPAWNING
-- Auto-creates zones so the user never has to find GUIDs
---------------------------------------------------------------

-- Zone label colors so you can tell them apart
local ZONE_COLORS = {
    battlefield = {0.1, 0.9, 0.1, 0.4},  -- bright green, semi-transparent
    graveyard   = {0.9, 0.2, 0.2, 0.4},  -- red, semi-transparent
    exile       = {0.2, 0.4, 0.9, 0.4},  -- blue, semi-transparent
}

function spawnZoneMarker(zoneConfig, zoneName, playerColor)
    -- Spawn a flat block as a visual indicator for where the zone is
    -- BlockSquare base size is ~1.2 TTS units, so divide zone scale by 1.2 to match
    local marker = spawnObject({
        type = "BlockSquare",
        position = {zoneConfig.position[1], 1.01, zoneConfig.position[3]},
        rotation = {0, 0, 0},
        scale = {zoneConfig.scale[1] / 1.2, 0.01, zoneConfig.scale[3] / 1.2},
        sound = false,
        callback_function = function(obj)
            obj.setName("JudgeMarker_" .. playerColor .. "_" .. zoneName)
            obj.setLock(true)
            obj.setColorTint(ZONE_COLORS[zoneName] or {0.1, 0.9, 0.1, 0.4})
            obj.interactable = false
        end,
    })
    return marker
end

function spawnZones()
    ZONE_OBJECTS = {}
    ZONE_MARKERS = {}
    local zoneCount = 0

    for color, zones in pairs(ZONE_POSITIONS) do
        ZONE_OBJECTS[color] = {}
        ZONE_MARKERS[color] = {}
        for zoneName, zoneConfig in pairs(zones) do
            local zone = spawnObject({
                type = "ScriptingTrigger",
                position = zoneConfig.position,
                rotation = {0, 0, 0},
                scale = zoneConfig.scale,
                sound = false,
                callback_function = function(obj)
                    obj.setName("Judge_" .. color .. "_" .. zoneName)
                end,
            })
            ZONE_OBJECTS[color][zoneName] = zone

            -- Spawn visual marker
            if showMarkers then
                ZONE_MARKERS[color][zoneName] = spawnZoneMarker(zoneConfig, zoneName, color)
            end

            zoneCount = zoneCount + 1
        end
    end

    return zoneCount
end

function destroyAllMarkers()
    for _, obj in ipairs(getAllObjects()) do
        local name = obj.getName() or ""
        if name:match("^JudgeMarker_") then
            obj.destruct()
        end
    end
    ZONE_MARKERS = {}
end

function spawnAllMarkers()
    destroyAllMarkers()
    for color, zones in pairs(ZONE_POSITIONS) do
        ZONE_MARKERS[color] = {}
        for zoneName, zoneConfig in pairs(zones) do
            ZONE_MARKERS[color][zoneName] = spawnZoneMarker(zoneConfig, zoneName, color)
        end
    end
end

-- Find existing judge zones and markers (after a save/load cycle, they persist with names)
function findExistingZones()
    ZONE_OBJECTS = {}
    ZONE_MARKERS = {}
    local found = 0

    for _, obj in ipairs(getAllObjects()) do
        local name = obj.getName() or ""

        -- Match zone triggers
        local color, zoneName = name:match("^Judge_(%w+)_(%w+)$")
        if color and zoneName and ZONE_POSITIONS[color] and ZONE_POSITIONS[color][zoneName] then
            if not ZONE_OBJECTS[color] then
                ZONE_OBJECTS[color] = {}
            end
            ZONE_OBJECTS[color][zoneName] = obj
            found = found + 1
        end

        -- Match visual markers
        local mColor, mZone = name:match("^JudgeMarker_(%w+)_(%w+)$")
        if mColor and mZone then
            if not ZONE_MARKERS[mColor] then
                ZONE_MARKERS[mColor] = {}
            end
            ZONE_MARKERS[mColor][mZone] = obj
        end
    end

    return found
end

---------------------------------------------------------------
-- JUDGE MAT SETUP
-- Creates or finds the mat on table load
---------------------------------------------------------------

function onLoad(save_state)
    -- Restore saved API keys if any
    if save_state and save_state ~= "" then
        local saved = JSON.decode(save_state)
        if saved and saved.keys then
            PLAYER_KEYS = saved.keys
        end
    end

    -- Find or create scripting zones
    local existingZones = findExistingZones()
    if existingZones == 0 then
        local count = spawnZones()
        broadcastToAll("MTG AI Judge: Spawned " .. count .. " scripting zones. Type 'judge zones' to check positions.", {0.4, 0.7, 1.0})
    end

    -- Look for existing judge mat or create one
    for _, obj in ipairs(getAllObjects()) do
        if obj.getName() == "MTG AI Judge" then
            judgeMat = obj
            break
        end
    end

    if judgeMat == nil then
        -- Spawn a visible block as the judge mat (bottom-center edge of table)
        judgeMat = spawnObject({
            type = "BlockSquare",
            position = {-48, 1.2, 32},
            rotation = {0, 0, 0},
            scale = {3, 0.2, 1.5},
            callback_function = function(obj)
                obj.setName("MTG AI Judge")
                obj.setDescription("Type 'judge setup' to enter your API key")
                obj.setLock(true)
                obj.setColorTint({0.6, 0.2, 0.8})
            end,
        })
    end

    -- Load the Global UI XML (hidden by default)
    UI.setXml(API_KEY_UI)
end

function onSave()
    -- Persist API keys across saves
    return JSON.encode({ keys = PLAYER_KEYS })
end

---------------------------------------------------------------
-- GLOBAL UI CALLBACKS (API key dialog)
---------------------------------------------------------------

function onSaveKey(player, value, id)
    local apiKey = UI.getAttribute("apiKeyInput", "text") or ""
    apiKey = apiKey:gsub("%s+", "")  -- trim whitespace

    if apiKey == "" then
        printToColor("Please enter a valid API key.", player.color, {1, 0.3, 0.3})
        return
    end

    -- Store key for this player's color
    PLAYER_KEYS[player.color] = apiKey

    -- Hide dialog
    hideApiKeyDialog()

    -- Confirm privately
    printToColor("API key saved! Type 'judge' followed by your question in chat.", player.color, {0.2, 0.8, 0.2})
end

function onCancelKey(player, value, id)
    hideApiKeyDialog()
end

---------------------------------------------------------------
-- BOARD STATE SCRAPING
---------------------------------------------------------------

-- Get card names from a zone object reference
function getCardNamesInZone(zoneObj)
    local names = {}
    if zoneObj == nil then return names end

    local objects = zoneObj.getObjects()
    for _, obj in ipairs(objects) do
        if obj.type == "Card" then
            local name = obj.getName()
            if name and name ~= "" then
                table.insert(names, name)
            end
        elseif obj.type == "Deck" then
            -- Cards stacked in a deck (e.g., graveyard pile)
            local deckObjects = obj.getObjects()
            for _, card in ipairs(deckObjects) do
                if card.name and card.name ~= "" then
                    table.insert(names, card.name)
                end
            end
        end
    end
    return names
end

-- Count cards in a player's hand zone
function getHandCount(playerColor)
    local player = Player[playerColor]
    if player and player.seated then
        local handObjects = player.getHandObjects(1)
        if handObjects then
            return #handObjects
        end
    end
    return 0
end

-- Scrape the full board state for all players
function scrapeBoardState()
    local board_state = {}
    local life_totals = {}

    for color, _ in pairs(ZONE_POSITIONS) do
        local playerKey = COLOR_TO_PLAYER[color]
        local zones = ZONE_OBJECTS[color] or {}
        board_state[playerKey] = {
            battlefield = getCardNamesInZone(zones.battlefield),
            graveyard   = getCardNamesInZone(zones.graveyard),
            exile       = getCardNamesInZone(zones.exile),
            hand_count  = getHandCount(color),
        }
        -- Default life total; update if your table has counter objects
        life_totals[playerKey] = 20
    end

    return board_state, life_totals
end

-- Determine active player (falls back to the player who asked)
function getActivePlayer(senderColor)
    return COLOR_TO_PLAYER[senderColor] or "player1"
end

---------------------------------------------------------------
-- CHAT COMMAND HANDLER
---------------------------------------------------------------

function onChat(message, sender)
    -- Match "judge setup" command — show API key dialog
    if message:lower():match("^judge%s+setup%s*$") then
        showApiKeyDialog()
        return false
    end

    -- Match "judge clear" command
    if message:lower():match("^judge%s+clear%s*$") then
        printToColor("Session cleared. Your next question starts fresh.", sender.color, {0.8, 0.8, 0.2})
        return false  -- suppress from chat
    end

    -- Match "judge zones" command — show zone info for debugging
    if message:lower():match("^judge%s+zones%s*$") then
        printToColor("--- Zone Status ---", sender.color, {0.4, 0.7, 1.0})
        for color, zones in pairs(ZONE_OBJECTS) do
            for zoneName, zoneObj in pairs(zones) do
                local pos = zoneObj.getPosition()
                local count = #zoneObj.getObjects()
                printToColor(
                    color .. " " .. zoneName .. ": " .. count .. " objects (pos: " ..
                    string.format("%.0f, %.0f, %.0f", pos.x, pos.y, pos.z) .. ")",
                    sender.color, {0.7, 0.7, 0.7}
                )
            end
        end
        printToColor("Tip: Move cards into zones and run 'judge zones' again to verify detection.", sender.color, {0.8, 0.8, 0.2})
        return false
    end

    -- Match "judge reset zones" — delete and respawn all zones
    if message:lower():match("^judge%s+reset%s+zones%s*$") then
        -- Delete existing zones and markers
        for color, zones in pairs(ZONE_OBJECTS) do
            for zoneName, zoneObj in pairs(zones) do
                if zoneObj then zoneObj.destruct() end
            end
        end
        ZONE_OBJECTS = {}
        destroyAllMarkers()
        -- Respawn
        local count = spawnZones()
        printToColor("Respawned " .. count .. " scripting zones.", sender.color, {0.4, 0.7, 1.0})
        return false
    end

    -- Match "judge hide zones" — hide the colored zone markers
    if message:lower():match("^judge%s+hide%s+zones%s*$") then
        showMarkers = false
        destroyAllMarkers()
        printToColor("Zone markers hidden. Type 'judge show zones' to show them again.", sender.color, {0.4, 0.7, 1.0})
        return false
    end

    -- Match "judge show zones" — show the colored zone markers
    if message:lower():match("^judge%s+show%s+zones%s*$") then
        showMarkers = true
        spawnAllMarkers()
        printToColor("Zone markers visible.", sender.color, {0.4, 0.7, 1.0})
        return false
    end

    -- Match "judge <question>" command
    local question = message:match("^[Jj]udge%s+(.+)$")
    if question == nil then
        return true  -- not a judge command, pass through
    end

    -- Check for API key
    local apiKey = PLAYER_KEYS[sender.color]
    if apiKey == nil or apiKey == "" then
        printToColor("No API key set. Type 'judge setup' to enter your Anthropic API key.", sender.color, {1, 0.3, 0.3})
        return false
    end

    -- Notify player
    printToColor("Consulting the judge...", sender.color, {0.8, 0.8, 0.2})

    -- Scrape board state
    local board_state, life_totals = scrapeBoardState()
    local active_player = getActivePlayer(sender.color)

    -- Session ID based on player color for conversation continuity
    local session_id = sender.color:lower()

    -- Build request payload
    local requestBody = JSON.encode({
        question      = question,
        board_state   = board_state,
        life_totals   = life_totals,
        active_player = active_player,
        api_key       = apiKey,
        session_id    = session_id,
    })

    -- Send to server
    local headers = {
        ["Content-Type"] = "application/json",
    }

    WebRequest.custom(
        SERVER_URL,
        "POST",
        true,
        requestBody,
        headers,
        function(req)
            handleJudgeResponse(req, sender)
        end
    )

    return false  -- suppress the judge command from chat
end

---------------------------------------------------------------
-- RESPONSE HANDLER
---------------------------------------------------------------

function handleJudgeResponse(req, sender)
    -- Network error
    if req.is_error then
        printToColor("Judge error: " .. (req.error or "Unknown network error"), sender.color, {1, 0.3, 0.3})
        return
    end

    -- HTTP error
    if req.response_code ~= 200 then
        printToColor("Judge server returned code " .. req.response_code, sender.color, {1, 0.3, 0.3})
        return
    end

    -- Parse JSON response
    local ok, response = pcall(JSON.decode, req.text)
    if not ok or response == nil then
        printToColor("Failed to parse judge response.", sender.color, {1, 0.3, 0.3})
        return
    end

    -- Format the ruling for display
    local output = "\n[b]=== JUDGE RULING ===[/b]\n"
    output = output .. (response.ruling or "No ruling provided.") .. "\n\n"
    output = output .. "[i]EXPLANATION:[/i]\n"
    output = output .. (response.explanation or "") .. "\n"

    if response.rules_cited and #response.rules_cited > 0 then
        output = output .. "\n[b]Rules:[/b] " .. table.concat(response.rules_cited, ", ")
    end

    if response.cards_referenced and #response.cards_referenced > 0 then
        output = output .. "\n[b]Cards:[/b] " .. table.concat(response.cards_referenced, ", ")
    end

    if response.web_sources and #response.web_sources > 0 then
        output = output .. "\n[i]Sources:[/i] " .. table.concat(response.web_sources, ", ")
    end

    output = output .. "\n[b]====================[/b]"

    -- Broadcast to all players so everyone sees the ruling
    broadcastToAll(output, {0.4, 0.7, 1.0})
end
