;;; codexa.el --- CodexA integration for Emacs -*- lexical-binding: t; -*-

;; Author: M9nx
;; Version: 0.5.0
;; Package-Requires: ((emacs "27.1") (json "1.5"))
;; Keywords: tools, code, search
;; URL: https://github.com/m9nx/codexa

;;; Commentary:

;; Provides semantic code search, symbol explanation, and re-indexing
;; via the CodexA bridge server (codexa serve).
;;
;; Usage:
;;   M-x codexa-search       — Semantic search with minibuffer results
;;   M-x codexa-explain      — Explain symbol at point
;;   M-x codexa-reindex      — Trigger re-index
;;
;; Works with helm, ivy, and default completing-read.

;;; Code:

(require 'json)
(require 'url)

(defgroup codexa nil
  "CodexA semantic code intelligence."
  :group 'tools
  :prefix "codexa-")

(defcustom codexa-bridge-url "http://localhost:24842"
  "URL of the CodexA bridge server."
  :type 'string
  :group 'codexa)

(defcustom codexa-top-k 10
  "Number of search results to return."
  :type 'integer
  :group 'codexa)

(defun codexa--bridge-post (endpoint body)
  "POST BODY (alist) to ENDPOINT on the CodexA bridge server.
Returns parsed JSON or nil on error."
  (let* ((url-request-method "POST")
         (url-request-extra-headers '(("Content-Type" . "application/json")))
         (url-request-data (json-encode body))
         (url (concat codexa-bridge-url endpoint)))
    (condition-case err
        (with-current-buffer (url-retrieve-synchronously url t nil 10)
          (goto-char url-http-end-of-headers)
          (json-read))
      (error (message "CodexA error: %s — is 'codexa serve' running?" err)
             nil))))

;;;###autoload
(defun codexa-search (query)
  "Search the codebase with QUERY using CodexA semantic search."
  (interactive "sCodexA Search: ")
  (let* ((resp (codexa--bridge-post
                "/request"
                `((kind . "semantic_search")
                  (params . ((query . ,query) (top_k . ,codexa-top-k))))))
         (data (and resp (cdr (assq 'data resp))))
         (results (and data (cdr (assq 'results data)))))
    (if (not results)
        (message "No results for: %s" query)
      ;; Populate a compilation-style buffer
      (with-current-buffer (get-buffer-create "*CodexA Results*")
        (let ((inhibit-read-only t))
          (erase-buffer)
          (insert (format "CodexA search: %s\n\n" query))
          (seq-doseq (r results)
            (let ((fp (cdr (assq 'file_path r)))
                  (ln (or (cdr (assq 'start_line r)) 1))
                  (snippet (substring (or (cdr (assq 'content r)) "") 0
                                      (min 120 (length (or (cdr (assq 'content r)) ""))))))
              (insert (format "%s:%d: %s\n" fp ln (replace-regexp-in-string "\n" " " snippet)))))
          (goto-char (point-min))
          (grep-mode)))
      (display-buffer "*CodexA Results*"))))

;;;###autoload
(defun codexa-explain ()
  "Explain the symbol at point using CodexA."
  (interactive)
  (let* ((sym (thing-at-point 'symbol t))
         (resp (codexa--bridge-post
                "/request"
                `((kind . "explain_symbol")
                  (params . ((symbol_name . ,sym))))))
         (data (and resp (cdr (assq 'data resp)))))
    (if (not data)
        (message "No info for: %s" sym)
      (with-current-buffer (get-buffer-create "*CodexA Explain*")
        (let ((inhibit-read-only t))
          (erase-buffer)
          (insert (json-encode data))
          (json-pretty-print-buffer)
          (goto-char (point-min)))
        (special-mode))
      (display-buffer "*CodexA Explain*"))))

;;;###autoload
(defun codexa-reindex ()
  "Trigger a CodexA re-index."
  (interactive)
  (codexa--bridge-post
   "/request"
   '((kind . "invoke_tool")
     (params . ((tool_name . "reindex") (arguments . ((force . :json-false)))))))
  (message "CodexA: Re-index triggered"))

(provide 'codexa)
;;; codexa.el ends here
