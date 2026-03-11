-- codexa.nvim — Neovim integration for CodexA
-- Provides semantic search via telescope.nvim, floating preview, and LSP integration.

local M = {}

M.config = {
    bridge_url = "http://localhost:24842",
    top_k = 10,
    keymap_search = "<leader>cs",
    keymap_explain = "<leader>ce",
    keymap_reindex = "<leader>ci",
}

--- HTTP POST request to the CodexA bridge server.
---@param endpoint string
---@param body string JSON body
---@param callback fun(data: string)
local function bridge_request(endpoint, body, callback)
    local cmd = string.format(
        'curl -s -X POST -H "Content-Type: application/json" -d %s %s%s',
        vim.fn.shellescape(body),
        M.config.bridge_url,
        endpoint
    )
    vim.fn.jobstart(cmd, {
        stdout_buffered = true,
        on_stdout = function(_, data)
            if data and data[1] ~= "" then
                callback(table.concat(data, "\n"))
            end
        end,
    })
end

--- Semantic search with telescope.nvim picker.
function M.semantic_search()
    local ok, telescope = pcall(require, "telescope.pickers")
    if not ok then
        vim.notify("telescope.nvim required for CodexA search", vim.log.levels.WARN)
        -- Fallback: input + quickfix
        vim.ui.input({ prompt = "CodexA Search: " }, function(query)
            if not query or query == "" then return end
            local body = vim.fn.json_encode({
                kind = "semantic_search",
                params = { query = query, top_k = M.config.top_k },
            })
            bridge_request("/request", body, function(resp)
                local data = vim.fn.json_decode(resp)
                if data and data.data and data.data.results then
                    local qf = {}
                    for _, r in ipairs(data.data.results) do
                        table.insert(qf, {
                            filename = r.file_path or "",
                            lnum = r.start_line or 1,
                            text = (r.content or ""):sub(1, 120),
                        })
                    end
                    vim.fn.setqflist(qf, "r")
                    vim.cmd("copen")
                end
            end)
        end)
        return
    end

    -- Full telescope picker
    local finders = require("telescope.finders")
    local conf = require("telescope.config").values
    local actions = require("telescope.actions")
    local action_state = require("telescope.actions.state")

    vim.ui.input({ prompt = "CodexA Search: " }, function(query)
        if not query or query == "" then return end
        local body = vim.fn.json_encode({
            kind = "semantic_search",
            params = { query = query, top_k = M.config.top_k },
        })
        bridge_request("/request", body, function(resp)
            vim.schedule(function()
                local data = vim.fn.json_decode(resp)
                if not data or not data.data or not data.data.results then
                    vim.notify("No results", vim.log.levels.INFO)
                    return
                end
                local results = data.data.results
                telescope.new({}, {
                    prompt_title = "CodexA: " .. query,
                    finder = finders.new_table({
                        results = results,
                        entry_maker = function(entry)
                            return {
                                value = entry,
                                display = string.format("%s:%d  %s",
                                    entry.file_path or "?",
                                    entry.start_line or 0,
                                    (entry.content or ""):sub(1, 80)),
                                ordinal = (entry.file_path or "") .. " " .. (entry.content or ""),
                                filename = entry.file_path,
                                lnum = entry.start_line or 1,
                            }
                        end,
                    }),
                    sorter = conf.generic_sorter({}),
                    attach_mappings = function(buf, map)
                        actions.select_default:replace(function()
                            local sel = action_state.get_selected_entry()
                            actions.close(buf)
                            if sel and sel.filename then
                                vim.cmd("edit " .. sel.filename)
                                vim.api.nvim_win_set_cursor(0, { sel.lnum, 0 })
                            end
                        end)
                        return true
                    end,
                }):find()
            end)
        end)
    end)
end

--- Explain the symbol under the cursor.
function M.explain_symbol()
    local word = vim.fn.expand("<cword>")
    if word == "" then
        vim.notify("No symbol under cursor", vim.log.levels.WARN)
        return
    end
    local body = vim.fn.json_encode({
        kind = "explain_symbol",
        params = { symbol_name = word },
    })
    bridge_request("/request", body, function(resp)
        vim.schedule(function()
            local data = vim.fn.json_decode(resp)
            if not data or not data.data then
                vim.notify("No info for: " .. word, vim.log.levels.INFO)
                return
            end
            -- Show in floating window
            local lines = vim.split(vim.inspect(data.data), "\n")
            local buf = vim.api.nvim_create_buf(false, true)
            vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
            local width = math.min(80, vim.o.columns - 4)
            local height = math.min(#lines, 20)
            vim.api.nvim_open_win(buf, true, {
                relative = "cursor",
                width = width,
                height = height,
                row = 1,
                col = 0,
                style = "minimal",
                border = "rounded",
            })
        end)
    end)
end

--- Trigger re-index.
function M.reindex()
    local body = vim.fn.json_encode({
        kind = "invoke_tool",
        params = { tool_name = "reindex", arguments = { force = false } },
    })
    bridge_request("/request", body, function(resp)
        vim.schedule(function()
            vim.notify("CodexA: Re-index complete", vim.log.levels.INFO)
        end)
    end)
end

--- Setup keymaps and user commands.
function M.setup(opts)
    M.config = vim.tbl_deep_extend("force", M.config, opts or {})

    vim.keymap.set("n", M.config.keymap_search, M.semantic_search, { desc = "CodexA: Semantic Search" })
    vim.keymap.set("n", M.config.keymap_explain, M.explain_symbol, { desc = "CodexA: Explain Symbol" })
    vim.keymap.set("n", M.config.keymap_reindex, M.reindex, { desc = "CodexA: Re-index" })

    vim.api.nvim_create_user_command("CodexaSearch", function() M.semantic_search() end, {})
    vim.api.nvim_create_user_command("CodexaExplain", function() M.explain_symbol() end, {})
    vim.api.nvim_create_user_command("CodexaReindex", function() M.reindex() end, {})
end

return M
