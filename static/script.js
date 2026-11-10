/**
 * Frontend logic for the AI Resume Rewriter.
 * Plain vanilla JavaScript — no frameworks, as per project requirements.
 */

const form            = document.getElementById('rewrite-form');
const resumeInput     = document.getElementById('resume-input');
const fileNameDisplay = document.getElementById('file-name-display');
const submitBtn       = document.getElementById('submit-btn');

const placeholderState = document.getElementById('placeholder-state');
const loadingState     = document.getElementById('loading-state');
const resultOutput     = document.getElementById('result-output');
const errorBox         = document.getElementById('error-box');
const copyBtn          = document.getElementById('copy-btn');

resumeInput.addEventListener('change', () => {
  if (resumeInput.files.length > 0) {
    fileNameDisplay.textContent = `Selected: ${resumeInput.files[0].name}`;
  } else {
    fileNameDisplay.textContent = 'No file selected.';
  }
});

function setState(state) {
  placeholderState.classList.add('hidden');
  loadingState.classList.add('hidden');
  resultOutput.classList.add('hidden');
  copyBtn.classList.add('hidden');
  errorBox.classList.add('hidden');

  if (state === 'placeholder') placeholderState.classList.remove('hidden');
  if (state === 'loading') loadingState.classList.remove('hidden');
  if (state === 'result') {
    resultOutput.classList.remove('hidden');
    copyBtn.classList.remove('hidden');
  }
  if (state === 'error') errorBox.classList.remove('hidden');
}

function renderMarkdown(markdown) {
  const escapeHtml = (str) =>
    str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const lines = escapeHtml(markdown).split('\n');
  let html = '';
  let inList = false;

  for (let rawLine of lines) {
    const line = rawLine.trim();
    const withBold = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    if (withBold.startsWith('### ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<h4>${withBold.slice(4)}</h4>`;
    } else if (withBold.startsWith('## ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<h3>${withBold.slice(3)}</h3>`;
    } else if (withBold.startsWith('# ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<h2>${withBold.slice(2)}</h2>`;
    } else if (withBold.startsWith('- ') || withBold.startsWith('* ')) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${withBold.slice(2)}</li>`;
    } else if (withBold === '') {
      if (inList) { html += '</ul>'; inList = false; }
    } else {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<p>${withBold}</p>`;
    }
  }
  if (inList) html += '</ul>';

  return html;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  if (resumeInput.files.length === 0) {
    showError('Please choose a PDF resume first.');
    return;
  }

  const formData = new FormData(form);

  submitBtn.disabled = true;
  submitBtn.textContent = 'Rewriting...';
  setState('loading');

  try {
    const response = await fetch('/rewrite', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      showError(data.error || 'Something went wrong. Please try again.');
      return;
    }

    resultOutput.innerHTML = renderMarkdown(data.result);
    setState('result');
  } catch (networkErr) {
    showError('Could not reach the server. Check your connection and try again.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Rewrite Resume';
  }
});

function showError(message) {
  errorBox.textContent = message;
  setState('error');
}

copyBtn.addEventListener('click', () => {
  navigator.clipboard.writeText(resultOutput.innerText).then(() => {
    copyBtn.textContent = 'Copied!';
    setTimeout(() => { copyBtn.textContent = 'Copy to Clipboard'; }, 1500);
  });
});
