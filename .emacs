;; http://www.emacswiki.org/emacs/ELPA
(setq package-archives '(("gnu" . "http://elpa.gnu.org/packages/")
                         ("marmalade" . "http://marmalade-repo.org/packages/")
                         ("melpa" . "http://melpa.milkbox.net/packages/")))

;; http://stackoverflow.com/questions/11127109/emacs-24-package-system-initialization-problems
(setq package-enable-at-startup nil)
(package-initialize)

(defvar starter-kit-packages
  (list 'evil
        'auto-complete
        'pos-tip
        'org
        'ace-jump-mode
        'htmlize
        'expand-region
        'adaptive-wrap
        'tabbar
        'web-mode
        ;'flycheck
        'go-mode
        'smartparens
        'js2-mode
        'undo-tree ; Automatically loaded by evil.
        'helm)
  "Libraries that should be installed by default.")

(defun starter-kit-elpa-install ()
  "Install all starter-kit packages that aren't installed."
  (interactive)
  (dolist (package starter-kit-packages)
    (unless (or (member package package-activated-list)
                (functionp package))
      (message "Installing %s" (symbol-name package))
      (package-install package))))


;; On your first run, this should pull in all the base packages.
(when (not package-archive-contents) (package-refresh-contents))
(starter-kit-elpa-install)

(load "server")
(unless (server-running-p) (server-start))

;; http://ergoemacs.org/emacs/emacs_make_modern.html
(column-number-mode 1)
(defvar backup-dir (expand-file-name "~/.emacs.d/backup/"))
(setq backup-directory-alist (list (cons ".*" backup-dir)))
(setq auto-save-default nil) ; stop creating those #autosave# files

;; Get middle click to work.
;; http://www.emacswiki.org/emacs/CopyAndPaste
(setq x-select-enable-primary t)
(setq select-active-regions t) ;  active region sets primary X11 selection
(global-set-key [mouse-2] 'mouse-yank-primary)

;; Better buffer management commands
;; http://ergoemacs.org/emacs/emacs_buffer_management.html
;;(ido-mode 1)
;;(defalias 'list-buffers 'ibuffer)


;; http://www.emacswiki.org/emacs/TabBarMode
(tabbar-mode t)
(global-set-key [C-prior] 'tabbar-backward)
(global-set-key [C-next] 'tabbar-forward)
(defun my-tabbar-buffer-groups () ;; customize to show all normal files in one group
   "Returns the name of the tab group names the current buffer belongs to.
 There are two groups: Emacs buffers (those whose name starts with '*', plus
 dired buffers), and the rest.  This works at least with Emacs v24.2 using
 tabbar.el v1.7."
   (list (cond ((string-equal "*" (substring (buffer-name) 0 1)) "emacs")
               ((eq major-mode 'dired-mode) "emacs")
               (t "user"))))
 (setq tabbar-buffer-groups-function 'my-tabbar-buffer-groups)

;; http://www.emacswiki.org/emacs/UndoTree
(undo-tree-mode t)

;; http://www.emacswiki.org/emacs/Evil
(require 'evil)
(setq evil-default-cursor t)
(evil-mode 1)

;; org mode
;; http://orgmode.org/worg/org-tutorials/orgtutorial_dto.html
;; http://orgmode.org/manual/Activation.html#Activation
(global-set-key "\C-cl" 'org-store-link)
(global-set-key "\C-cc" 'org-capture)
(global-set-key "\C-ca" 'org-agenda)
(global-set-key "\C-cb" 'org-iswitchb)

;; http://orgmode.org/manual/Clocking-work-time.html
(org-clock-persistence-insinuate)

;;;;;;;;;;;; AUTOCOMPLETION
; Enables tooltip help
(require 'pos-tip)

; setup autocompletion
(require 'auto-complete-config)
(setq-default ac-sources '(ac-source-dictionary ac-source-words-in-same-mode-buffers ac-source-filename))
(add-hook 'emacs-lisp-mode-hook 'ac-emacs-lisp-mode-setup)
(add-hook 'c-mode-common-hook 'ac-cc-mode-setup)
(add-hook 'css-mode-hook 'ac-css-mode-setup)
(setq ac-auto-start 0)
(setq ac-auto-show-menu t)
(setq ac-quick-help-delay 0.5)
(setq ac-candidate-limit 100)
(add-to-list 'ac-modes 'html-mode)
(add-to-list 'ac-modes 'web-mode)
(setq ac-disable-faces nil)
(global-auto-complete-mode t)

; Enter automatically indents
(define-key global-map (kbd "RET") 'newline-and-indent)

; Don't kill the windows on :bd
(evil-ex-define-cmd "bd[elete]" 'kill-this-buffer)

(defun comment-or-uncomment-region-or-line ()
   "Comments or uncomments the region or the current line if there's no active region."
   (interactive)
   (let (beg end)
     (if (region-active-p)
         (setq beg (region-beginning) end (region-end))
       (setq beg (line-beginning-position) end (line-end-position)))
     (if (string= "web-mode" major-mode)
         (web-mode-comment-or-uncomment)
         (comment-or-uncomment-region beg end))))

(define-key evil-normal-state-map (kbd "c") 'comment-or-uncomment-region-or-line)
(define-key evil-visual-state-map (kbd "c") 'comment-or-uncomment-region-or-line)

(require 'expand-region)
(define-key evil-normal-state-map (kbd "e") 'er/expand-region)
(define-key evil-visual-state-map (kbd "e") 'er/expand-region)
(define-key evil-normal-state-map (kbd "E") 'er/contract-region)
(define-key evil-visual-state-map (kbd "E") 'er/contract-region)

(require 'ace-jump-mode)
(define-key evil-normal-state-map (kbd "f") 'ace-jump-mode)

(require 'windmove)
(global-set-key (kbd "C-c <up>") 'windmove-up)
(global-set-key (kbd "C-c <down>") 'windmove-down)
(global-set-key (kbd "C-c <right>") 'windmove-right)
(global-set-key (kbd "C-c <left>") 'windmove-left)

;; Don't wait for any other keys after escape is pressed.
(setq evil-esc-delay 0)

(add-hook 'emacs-lisp-mode-hook (lambda ()
                            (define-key evil-normal-state-map (kbd ".") 'eval-last-sexp)))

(require 'helm-config)
(require 'helm)
(require 'helm-buffers)
(require 'helm-files)

(setq helm-mp-matching-method 'multi3p)
(setq helm-mp-highlight-delay 0.1)
(setq helm-M-x-always-save-history t)
(define-key evil-normal-state-map (kbd "t") 'helm-M-x)
(define-key evil-visual-state-map (kbd "t") 'helm-M-x)
(define-key evil-normal-state-map (kbd "s") 'helm-buffers-list)
(define-key evil-visual-state-map (kbd "s") 'helm-buffers-list)

(define-key helm-map (kbd "<escape>") 'helm-keyboard-quit)

;; Try to make buffer list more useful with similar names
(require 'uniquify)
(setq uniquify-buffer-name-style 'post-forward-angle-brackets)

(require 'recentf)
(setq recentf-exclude '("\\.recentf" "^/tmp/" "/.git/" "/.emacs.d/elpa/"))
(setq recentf-max-saved-items 100)
(setq recentf-auto-cleanup 'never)
(setq recentf-save-file (expand-file-name "~/.emacs.d/.recentf" user-emacs-directory))
(setq recentf-auto-save-timer
      (run-with-idle-timer 30 t 'recentf-save-list))
(recentf-mode 1)

(defvar helm-source-myrecent
  `((name . "Recentf")
    (candidates . (lambda () recentf-list))
    (no-delay-on-input)
    (action . (("Find file" . find-file)))))
(defun my-helm ()
  (interactive)
  (helm-other-buffer
   '(
     helm-source-myrecent
     helm-c-source-buffers-list)
   " *my-helm*"))

(define-key evil-normal-state-map (kbd ",") 'my-helm)

;(require 'flycheck)
;(setq flycheck-checkers (delq 'html-tidy flycheck-checkers))
;(global-flycheck-mode)

(require 'web-mode)
(add-to-list 'auto-mode-alist '("\\.html?\\'" . web-mode))
(add-to-list 'auto-mode-alist '("\\.js\\'" . js2-mode))

(require 'smartparens-config)
(show-smartparens-global-mode nil)
(smartparens-global-mode t)

; Indentation
(setq-default indent-tabs-mode nil)
(setq-default tab-width 8)
(setq c-basic-offset 2)
(setq css-indent-offset 2)
(setq web-mode-markup-indent-offset 2)
(setq web-mode-css-indent-offset 2)
(setq web-mode-code-indent-offset 2)
(setq-default evil-shift-width 2)

; wrapping
(global-visual-line-mode 1)

; (global-hl-line-mode 0)
; Save minibuffer history.
(savehist-mode 1)

(require 'saveplace)
(setq-default save-place t)

; Refresh all buffers periodically.
(setq revert-without-query '(".*"))
(global-auto-revert-mode t)

; Persistent undo!
(setq undo-tree-auto-save-history t)
(setq undo-tree-history-directory-alist '((".*" . "~/.emacs.d/undo")))

; Tail the compilation buffer.
(setq compilation-scroll-output t)

(when (string= system-name "ryanofsky.nyc.corp.google.com")
  ; go/emacs
  (require 'google)
  (require 'googlemenu)               ;; handy Google menu bar
  (require 'google3)                  ;; magically set paths for compiling google3 code
  (require 'google3-build)            ;; support for blaze builds
  (require 'csearch)                  ;; Search the whole Google code base.
  (setq google-build-system "blaze")
  (define-key evil-normal-state-map (kbd "b") 'google3-build)
  (define-key evil-visual-state-map (kbd "b") 'google3-build)
  (global-set-key [f7] 'google-show-tag-locations-regexp)
  (global-set-key [f8] 'google-show-callers)
  (global-set-key [f9] 'google-pop-tag)
  (global-set-key [f10] 'google-show-matching-tags)
  (setq browse-url-browser-function 'browse-url-generic
        browse-url-generic-program "google-chrome-stable"))

(setq mouse-wheel-scroll-amount '(1 ((shift) . 1) ((control) . nil)))
(setq mouse-wheel-progressive-speed t)

;; http://orgmode.org/guide/Publishing.html
(require 'ox-publish)
(setq org-publish-project-alist
      '(
        ("org-notes"
         :base-directory "~/google/"
         :base-extension "org"
         :publishing-directory "~/public_html/"
         :recursive t
         :publishing-function org-html-publish-to-html
         :headline-levels 4       ; Just the default for this project.
         :auto-preamble t
         :html-head "<link rel=\"stylesheet\" type=\"text/css\" href=\"css/solarized-light.min.css\" />
                     <link rel=\"stylesheet\" type=\"text/css\" href=\"css/russ.css\" />"
         :with-sub-superscript nil
         :section-numbers nil
         :with-drawers t
         :html-postamble ry/post
         )
        ("org-static"
         :base-directory "~/google/2014/org-static/"
         :base-extension "css\\|js\\|png\\|jpg\\|gif\\|pdf\\|mp3\\|ogg\\|swf"
         :publishing-directory "~/public_html/"
         :recursive t
         :publishing-function org-publish-attachment)
        ("org" :components ("org-notes" "org-static"))))

(add-to-list 'auto-mode-alist '("\\.org_archive$" . org-mode))

(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(clean-buffer-list-delay-general 0)
 '(custom-enabled-themes (quote (tango-dark)))
 '(debug-on-error nil)
 '(evil-search-module (quote evil-search))
 '(evil-want-fine-undo t)
 '(inhibit-startup-screen t)
 '(lazy-highlight-cleanup nil)
 '(org-adapt-indentation t)
 '(org-agenda-custom-commands (quote (("n" "Agenda and all TODO's" ((agenda "" nil) (alltodo "" nil)) nil) ("r" "Russ Agenda" agenda "" ((org-agenda-overriding-header "Russ Agenda") (org-agenda-view-columns-initially nil) (org-agenda-overriding-columns-format "%80ITEM %TAGS %7TODO %5Effort{:} %6CLOCKSUM{Total}") (org-agenda-start-with-log-mode (quote (closed clock state))) (org-agenda-span (quote month)))) ("q" "Russ Todos" alltodo "" ((org-agenda-view-columns-initially t) (org-agenda-overriding-columns-format "%80ITEM %TAGS %7TODO %20SCHEDULED %5Effort{:} %6CLOCKSUM{Total}") (org-agenda-skip-function (quote (org-agenda-skip-entry-if (quote todo) (quote ("DEFERRED"))))) (org-agenda-sorting-strategy (quote (scheduled-up effort-up)))) ("~/public_html/todo.html")))))
 '(org-agenda-files (quote ("~/google/log.org" "~/google/todo.org" "~/google/todo.org_archive" "~/russ/log.org" "~/russ/todo.org" "~/russ/todo.org_archive")))
 '(org-agenda-log-mode-add-notes t)
 '(org-agenda-skip-deadline-if-done t)
 '(org-agenda-start-on-weekday nil)
 '(org-archive-location "%s_archive::datetree/")
 '(org-archive-save-context-info (quote (time file category todo itags olpath)))
 '(org-capture-templates (quote (("t" "Todo" entry (file+headline "~/russ/todo.org" "Tasks") "* TODO %^{Brief Description} %^g
%?
Added: %U") ("i" "Idea" entry (file+datetree "~/russ/ideas.org") "* %?
Entered on %U
  %i
  %a"))))
 '(org-clock-continuously t)
 '(org-clock-idle-time 5)
 '(org-clock-into-drawer "LOGBOOK")
 '(org-clock-persist t)
 '(org-clock-persist-query-resume nil)
 '(org-datetree-add-timestamp (quote inactive))
 '(org-directory "~/google")
 '(org-export-with-drawers t)
 '(org-global-properties (quote (("Effort_ALL" . "0 0:10 0:30 1:00 2:00 3:00 4:00 8:00 16:00 24:00 40:00"))))
 '(org-hide-leading-stars t)
 '(org-link-search-must-match-exact-headline nil)
 '(org-log-into-drawer t)
 '(org-log-note-clock-out t)
 '(org-log-states-order-reversed nil)
 '(org-odd-levels-only t)
 '(org-return-follows-link t)
 '(org-special-ctrl-a/e (quote (t . reversed)))
 '(org-special-ctrl-k t)
 '(org-time-clocksum-use-fractional t)
 '(org-todo-keywords (quote ((sequence "TODO(t)" "BLOCKED(b@/@)" "DEFERRED(r)" "|" "DONE(d@/@)" "NVM(n@/@)")))))
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )

(defun ry/yagenda (agenda-cmd year)
       "Return agenda command with year timespan."
  (let*
    ((ok agenda-cmd)
    (cmd (copy-tree ok))
    (options (nth 4 cmd)))
    (setq options (delq (assoc 'org-agenda-span options) options))
    (push `(org-agenda-span 'year) options)
    (push `(org-agenda-start-day ,(concat year "-01-01")) options)
    (setf (nth 0 cmd) year)
    (setf (nth 0 cmd) (concat year " Agenda"))
    (setf (nth 4 cmd) options)
    (append cmd `(,(concat "~/public_html/" year ".html")))))

(defun ry/publish-agenda ()
       "Return agenda command with year timespan."
  (let*
   ((cmd (nth 1 org-agenda-custom-commands))
    (org-agenda-custom-commands
     `(,(ry/yagenda cmd "2013")
       ,(ry/yagenda cmd "2014")))
     )
    (org-batch-store-agenda-views)
   ))

(defun ry/post (info)
  ""
  (let ((spec (org-html-format-spec info)))
    (let ((date (cdr (assq ?d spec)))
          (author (cdr (assq ?a spec)))
          (email (cdr (assq ?e spec)))
          (creator (cdr (assq ?c spec))))
      (format "
<p class=\"author\">%s: %s</p>\n
<p class=\"date\">%s: %s</p>\n
<p class=\"creator\">%s</p>\n
<p class=\"source\"><a href=\"https://user.git.corp.google.com/ryanofsky/home/+/master/google/%s\">Source</a></p>"
              (org-html--translate "Author" info)
              author
              (org-html--translate "Created" info)
              (format-time-string org-html-metadata-timestamp-format)
              creator
              (file-name-nondirectory (plist-get info :input-file))
              ))))

;;; .emacs ends here
