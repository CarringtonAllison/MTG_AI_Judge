--[[
    MTG AI Judge Mod for Tabletop Simulator
    Works with "Oops I Baked a Pie" 4-player table

    Features:
    - Clickable Judge Mat for API key setup (no chat commands needed)
    - "judge <question>" chat command for rulings
    - "judge clear" to reset conversation session
    - Board state scraping (battlefield, graveyard, exile, hand)
    - Session-based conversation memory for follow-up questions
    - Broadcasts rulings to all players
]]

---------------------------------------------------------------
-- CONFIGURATION
---------------------------------------------------------------

-- Server URL — update this after deployment
local SERVER_URL = "http://localhost:8080/judge"

-- Per-player API keys stored in memory (color -> key)
local PLAYER_KEYS = {}

-- Zone GUIDs for "Oops I Baked a Pie" table
-- Load the table in TTS, right-click each zone, note GUID, fill in below
local ZONE_GUIDS = {
    White = { battlefield = "", graveyard = "", exile = "" },
    Blue  = { battlefield = "", graveyard = "", exile = "" },
    Red   = { battlefield = "", graveyard = "", exile = "" },
    Green = { battlefield = "", graveyard = "", exile = "" },
}

-- Map player seat colors to player keys used in the API
local COLOR_TO_PLAYER = {
    White = "player1",
    Blue  = "player2",
    Red   = "player3",
    Green = "player4",
}

-- Judge Mat object reference
local judgeMat = nil

---------------------------------------------------------------
-- JUDGE MAT UI (XML)
-- Renders a small panel on the mat with status + setup button
---------------------------------------------------------------

local function getMatUI(playerColor)
    local isReady = PLAYER_KEYS[playerColor] ~= nil
    local statusText = isReady and "Ready" or "Not Connected"
    local statusColor = isReady and "#4CAF50" or "#F44336"

    return [[
<Panel position="0 0.5 0" rotation="180 0 0" height="200" width="400">
  <VerticalLayout padding="10 10 10 10" spacing="5">
    <Text fontSize="24" font="Arial" color="#FFFFFF" alignment="MiddleCenter">MTG AI Judge</Text>
    <Text fontSize="16" font="Arial" color="]] .. statusColor .. [[" alignment="MiddleCenter">]] .. statusText .. [[</Text>
    <Button onClick="onSetupClick" fontSize="14" color="#FFFFFF" textColor="#000000">Enter API Key</Button>
  </VerticalLayout>
</Panel>
<Panel id="keyInputPanel" active="false" position="0 2 0" rotation="180 0 0" height="150" width="500">
  <VerticalLayout padding="10 10 10 10" spacing="5">
    <Text fontSize="16" font="Arial" color="#FFFFFF" alignment="MiddleCenter">Paste your Anthropic API Key:</Text>
    <InputField id="apiKeyInput" fontSize="14" characterLimit="200" placeholder="sk-ant-..." />
    <HorizontalLayout spacing="10">
      <Button onClick="onSaveKey" fontSize="14" color="#4CAF50" textColor="#FFFFFF">Save</Button>
      <Button onClick="onCancelKey" fontSize="14" color="#F44336" textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]]
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

    -- Look for existing judge mat or create one
    for _, obj in ipairs(getAllObjects()) do
        if obj.getName() == "MTG AI Judge" then
            judgeMat = obj
            break
        end
    end

    if judgeMat == nil then
        -- Spawn a custom tile as the judge mat
        judgeMat = spawnObject({
            type = "Custom_Tile",
            position = {0, 1.5, 0},
            rotation = {0, 0, 0},
            scale = {2, 1, 2},
            callback_function = function(obj)
                obj.setName("MTG AI Judge")
                obj.setDescription("Click to set up your API key, then type 'judge <question>' in chat")
                obj.setLock(true)
                obj.setColorTint({0.2, 0.1, 0.3})
                updateMatUI()
            end,
        })
    else
        Wait.time(updateMatUI, 1)
    end
end

function onSave()
    -- Persist API keys across saves
    return JSON.encode({ keys = PLAYER_KEYS })
end

---------------------------------------------------------------
-- MAT UI UPDATE
---------------------------------------------------------------

function updateMatUI()
    if judgeMat == nil then return end
    -- Default UI for first player who looks at it
    judgeMat.UI.setXml(getMatUI(nil))
end

---------------------------------------------------------------
-- MAT UI CALLBACKS
---------------------------------------------------------------

function onSetupClick(player, value, id)
    -- Show the key input panel for this player
    if judgeMat then
        judgeMat.UI.setAttribute("keyInputPanel", "active", "true")
    end
end

function onSaveKey(player, value, id)
    if judgeMat == nil then return end

    local apiKey = judgeMat.UI.getAttribute("apiKeyInput", "text") or ""
    apiKey = apiKey:gsub("%s+", "")  -- trim whitespace

    if apiKey == "" then
        printToColor("Please enter a valid API key.", player.color, {1, 0.3, 0.3})
        return
    end

    -- Store key for this player's color
    PLAYER_KEYS[player.color] = apiKey

    -- Hide input panel
    judgeMat.UI.setAttribute("keyInputPanel", "active", "false")

    -- Update status
    judgeMat.UI.setXml(getMatUI(player.color))

    -- Confirm privately
    printToColor("API key saved! Type 'judge' followed by your question in chat.", player.color, {0.2, 0.8, 0.2})
end

function onCancelKey(player, value, id)
    if judgeMat then
        judgeMat.UI.setAttribute("keyInputPanel", "active", "false")
    end
end

---------------------------------------------------------------
-- BOARD STATE SCRAPING
---------------------------------------------------------------

-- Get card names from a scripting zone by GUID
function getCardNamesInZone(zoneGUID)
    local names = {}
    if zoneGUID == "" then return names end

    local zone = getObjectFromGUID(zoneGUID)
    if zone == nil then return names end

    local objects = zone.getObjects()
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

    for color, zones in pairs(ZONE_GUIDS) do
        local playerKey = COLOR_TO_PLAYER[color]
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
    -- Match "judge clear" command
    if message:lower():match("^judge%s+clear%s*$") then
        printToColor("Session cleared. Your next question starts fresh.", sender.color, {0.8, 0.8, 0.2})
        return false  -- suppress from chat
    end

    -- Match "judge <question>" command
    local question = message:match("^[Jj]udge%s+(.+)$")
    if question == nil then
        return true  -- not a judge command, pass through
    end

    -- Check for API key
    local apiKey = PLAYER_KEYS[sender.color]
    if apiKey == nil or apiKey == "" then
        printToColor("No API key set. Click the Judge Mat on the table to enter your Anthropic API key.", sender.color, {1, 0.3, 0.3})
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
