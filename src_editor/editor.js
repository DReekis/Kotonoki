import { Editor } from '@tiptap/core';
import Document from '@tiptap/extension-document';
import Paragraph from '@tiptap/extension-paragraph';
import Text from '@tiptap/extension-text';
import Bold from '@tiptap/extension-bold';
import Italic from '@tiptap/extension-italic';
import Underline from '@tiptap/extension-underline';
import Highlight from '@tiptap/extension-highlight';
import Blockquote from '@tiptap/extension-blockquote';
import Link from '@tiptap/extension-link';
import History from '@tiptap/extension-history';
import HardBreak from '@tiptap/extension-hard-break';

window.initKotonokiEditor = function({ elementId, inputId, toolbarId, placeholderText }) {
  const element = document.getElementById(elementId);
  const hiddenInput = document.getElementById(inputId);
  const toolbar = document.getElementById(toolbarId);

  if (!element || !hiddenInput) return null;

  const editor = new Editor({
    element: element,
    extensions: [
      Document,
      Paragraph,
      Text,
      Bold,
      Italic,
      Underline,
      Highlight.configure({
        multicolor: false,
        HTMLAttributes: {
          class: 'kotonoki-highlight',
        },
      }),
      Blockquote,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          rel: 'noopener noreferrer',
          target: '_blank',
        },
        protocols: ['http', 'https'],
      }),
      HardBreak,
      History,
    ],
    content: hiddenInput.value || '',
    onUpdate({ editor }) {
      const html = editor.getHTML();
      // Only keep content if not just an empty paragraph
      const isEmpty = editor.isEmpty;
      hiddenInput.value = isEmpty ? '' : html;

      // Dispatch change event for draft autosave
      hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
      updateToolbarState();
    },
    onSelectionUpdate() {
      updateToolbarState();
    },
  });

  function updateToolbarState() {
    if (!toolbar) return;
    const buttons = toolbar.querySelectorAll('[data-command]');
    buttons.forEach(btn => {
      const command = btn.getAttribute('data-command');
      let isActive = false;
      if (command === 'bold') isActive = editor.isActive('bold');
      else if (command === 'italic') isActive = editor.isActive('italic');
      else if (command === 'underline') isActive = editor.isActive('underline');
      else if (command === 'highlight') isActive = editor.isActive('highlight');
      else if (command === 'blockquote') isActive = editor.isActive('blockquote');
      else if (command === 'link') isActive = editor.isActive('link');

      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
  }

  if (toolbar) {
    toolbar.addEventListener('click', (e) => {
      const button = e.target.closest('[data-command]');
      if (!button) return;
      e.preventDefault();

      const command = button.getAttribute('data-command');
      editor.commands.focus();

      if (command === 'bold') editor.chain().focus().toggleBold().run();
      else if (command === 'italic') editor.chain().focus().toggleItalic().run();
      else if (command === 'underline') editor.chain().focus().toggleUnderline().run();
      else if (command === 'highlight') editor.chain().focus().toggleHighlight().run();
      else if (command === 'blockquote') editor.chain().focus().toggleBlockquote().run();
      else if (command === 'undo') editor.chain().focus().undo().run();
      else if (command === 'redo') editor.chain().focus().redo().run();
      else if (command === 'link') {
        const previousUrl = editor.getAttributes('link').href;
        const url = window.prompt('Enter link URL (https://...):', previousUrl || 'https://');
        if (url === null) return;
        if (url === '' || url === 'https://') {
          editor.chain().focus().extendMarkRange('link').unsetLink().run();
        } else {
          editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
        }
      }
    });
  }

  return editor;
};
