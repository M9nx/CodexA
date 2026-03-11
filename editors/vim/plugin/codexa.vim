" codexa.vim — Lightweight Vim plugin for CodexA
" Provides semantic search via quickfix and symbol explanation.

if exists('g:loaded_codexa')
  finish
endif
let g:loaded_codexa = 1

let g:codexa_bridge_url = get(g:, 'codexa_bridge_url', 'http://localhost:24842')
let g:codexa_top_k = get(g:, 'codexa_top_k', 10)

function! s:BridgePost(endpoint, body) abort
  let l:cmd = 'curl -s -X POST -H "Content-Type: application/json"'
        \ . ' -d ' . shellescape(a:body)
        \ . ' ' . g:codexa_bridge_url . a:endpoint
  return system(l:cmd)
endfunction

function! codexa#search() abort
  let l:query = input('CodexA Search: ')
  if empty(l:query) | return | endif
  let l:body = json_encode({
        \ 'kind': 'semantic_search',
        \ 'params': {'query': l:query, 'top_k': g:codexa_top_k}
        \ })
  let l:resp = s:BridgePost('/request', l:body)
  try
    let l:data = json_decode(l:resp)
    if has_key(l:data, 'data') && has_key(l:data.data, 'results')
      let l:qf = []
      for l:r in l:data.data.results
        call add(l:qf, {
              \ 'filename': get(l:r, 'file_path', ''),
              \ 'lnum': get(l:r, 'start_line', 1),
              \ 'text': strpart(get(l:r, 'content', ''), 0, 120)
              \ })
      endfor
      call setqflist(l:qf, 'r')
      copen
    else
      echo 'No results'
    endif
  catch
    echoerr 'CodexA: ' . v:exception
  endtry
endfunction

function! codexa#explain() abort
  let l:word = expand('<cword>')
  if empty(l:word) | echo 'No symbol under cursor' | return | endif
  let l:body = json_encode({
        \ 'kind': 'explain_symbol',
        \ 'params': {'symbol_name': l:word}
        \ })
  let l:resp = s:BridgePost('/request', l:body)
  echo l:resp
endfunction

command! CodexaSearch call codexa#search()
command! CodexaExplain call codexa#explain()

nnoremap <silent> <leader>cs :CodexaSearch<CR>
nnoremap <silent> <leader>ce :CodexaExplain<CR>
