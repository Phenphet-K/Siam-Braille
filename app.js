/**
 * TBTW Modern - Main Application Controller
 * มาตรฐานการใช้อักษรเบรลล์ในประเทศไทย ฉบับปรับปรุง พ.ศ. 2564
 */

import { ThaiBrailleTranslator } from './js/translator.js';
import { BrailleEmbosser } from './js/embosser.js';
import { VirtualPerkinsKeyboard } from './js/virtual-keyboard.js';
import { UNICODE_TO_ASCII, unicodeToDots, dotsToUnicode } from './js/braille-core.js';

// Predefined test samples from the 2564 manual
const TEST_SAMPLES = {
  basic: "บ้านนี้มีพ่อ แม่ และลูกสองคน กำลังช่วยกันเก็บกวาดสวนมะลิ",
  grade2_prefix: "การทำงานบางอย่างต้องอาศัยกำลังและความอดทนสูง เช่น การเดินทางข้ามจังหวัด",
  grade2_roots: "ประชาชนทุกคนควรมีความสามารถในการพัฒนาตนเองตามธรรมชาติและหน้าที่ของพลเมืองที่ดี",
  grade2_etaikhu: "เด็กนักเรียนเจ็ดคนเห็นลูกแมวตัวเล็กเก็บอาหารอยู่ในกล่องเข็มหมุด",
  grade2_phrases: "นายกรัฐมนตรีกล่าวว่า ประเทศไทยจะก้าวไปข้างหน้า โดยเฉพาะอย่างยิ่งด้านการศึกษา ดังต่อไปนี้",
  numbers_dates: "เมื่อวันที่ ๑๒ ตุลาคม พ.ศ. 2564 มียอดจำหน่ายหนังสือจำนวน 1,240 เล่ม เวลา 10:30 น. ราคา 250.50 บาท",
  full_story: "พระบาทสมเด็จพระเจ้าอยู่หัว ทรงมีพระมหากรุณาธิคุณต่อพสกนิกรชาวไทยทุกหมู่เหล่า\n\nการศึกษาอักษรเบรลล์เป็นเครื่องมือสำคัญอย่างยิ่งสำหรับผู้พิการทางสายตา ช่วยให้สามารถอ่าน เขียน และเข้าถึงความรู้ได้อย่างเท่าเทียมกันในสังคมประชาธิปไตย (พ.ศ. 2564)"
};

class TBTWApp {
  constructor() {
    this.translator = new ThaiBrailleTranslator({ grade: 1 });
    this.embosser = new BrailleEmbosser({
      cellsPerLine: 40,
      linesPerPage: 25,
      pageNumberLocation: 'top-right'
    });

    this.currentGrade = 1;
    this.currentTab = 'unicode';
    this.brailleScale = 1.0;
    this.currentTheme = localStorage.getItem('tbtw_theme') || 'dark';
    this.debounceTimer = null;
    this.activeResult = null;
    this.selectedCellIndex = null;

    this.initElements();
    this.initKeyboard();
    this.bindEvents();
    this.applyTheme(this.currentTheme);

    // Initial translation if default text exists
    if (!this.inputSource.value.trim()) {
      this.inputSource.value = TEST_SAMPLES.basic;
    }
    this.translateNow();
  }

  initElements() {
    // Header & Actions
    this.btnGrade1 = document.getElementById('btnGrade1');
    this.btnGrade2 = document.getElementById('btnGrade2');
    this.btnPerkinsToggle = document.getElementById('btnPerkinsToggle');
    this.btnPageSetup = document.getElementById('btnPageSetup');
    this.btnThemeToggle = document.getElementById('btnThemeToggle');

    // Perkins Drawer
    this.perkinsDrawer = document.getElementById('perkinsDrawer');
    this.btnClosePerkins = document.getElementById('btnClosePerkins');
    this.btnCommitTouch = document.getElementById('btnCommitTouch');
    this.keySpace = document.getElementById('keySpace');
    this.liveChordCell = document.getElementById('liveChordCell');
    this.liveChordChar = document.getElementById('liveChordChar');
    this.perkinsKeys = {
      1: document.getElementById('keyDot1'),
      2: document.getElementById('keyDot2'),
      3: document.getElementById('keyDot3'),
      4: document.getElementById('keyDot4'),
      5: document.getElementById('keyDot5'),
      6: document.getElementById('keyDot6')
    };

    // Toolbar
    this.selectSample = document.getElementById('selectSample');
    this.fileInput = document.getElementById('fileInput');
    this.btnClear = document.getElementById('btnClear');
    this.btnSpeak = document.getElementById('btnSpeak');
    this.btnExportMenu = document.getElementById('btnExportMenu');
    this.exportDropdown = document.getElementById('exportDropdown');
    this.exportBRF = document.getElementById('exportBRF');
    this.exportUnicodeTxt = document.getElementById('exportUnicodeTxt');
    this.exportPEF = document.getElementById('exportPEF');
    this.printBraille = document.getElementById('printBraille');

    // Editor & Panes
    this.inputSource = document.getElementById('inputSource');
    this.sourceStats = document.getElementById('sourceStats');
    this.btnZoomIn = document.getElementById('btnZoomIn');
    this.btnZoomOut = document.getElementById('btnZoomOut');
    this.zoomLevel = document.getElementById('zoomLevel');
    this.btnCopyBraille = document.getElementById('btnCopyBraille');

    // Tabs & Views
    this.tabButtons = document.querySelectorAll('.tab-btn');
    this.viewUnicode = document.getElementById('viewUnicode');
    this.viewInteractive = document.getElementById('viewInteractive');
    this.viewSimBraille = document.getElementById('viewSimBraille');
    this.viewPaginated = document.getElementById('viewPaginated');

    this.outputUnicode = document.getElementById('outputUnicode');
    this.outputInteractive = document.getElementById('outputInteractive');
    this.outputSimBraille = document.getElementById('outputSimBraille');
    this.outputPaginated = document.getElementById('outputPaginated');

    // Inspector
    this.inspectorContent = document.getElementById('inspectorContent');

    // Status bar
    this.statusMode = document.getElementById('statusMode');
    this.statusCellsTotal = document.getElementById('statusCellsTotal');
    this.statusPagesTotal = document.getElementById('statusPagesTotal');
    this.statusPaperSize = document.getElementById('statusPaperSize');

    // Modal
    this.modalPageSetup = document.getElementById('modalPageSetup');
    this.btnCloseModal = document.getElementById('btnCloseModal');
    this.btnSavePageSetup = document.getElementById('btnSavePageSetup');
    this.cfgCellsPerLine = document.getElementById('cfgCellsPerLine');
    this.cfgLinesPerPage = document.getElementById('cfgLinesPerPage');
    this.cfgPageNumberLoc = document.getElementById('cfgPageNumberLoc');
  }

  initKeyboard() {
    this.perkinsKeyboard = new VirtualPerkinsKeyboard({
      onCellProduced: (cellData) => {
        this.insertBrailleCellAtCursor(cellData.unicode);
      },
      onBackspace: () => {
        this.deleteCharAtCursor();
      },
      onNewline: () => {
        this.insertCharAtCursor('\n');
      },
      onChordChange: (activeDots) => {
        this.updatePerkinsVisuals(activeDots);
      }
    });
  }

  bindEvents() {
    // 1. Text Input Real-time Translation
    this.inputSource.addEventListener('input', () => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.translateNow(), 70);
    });

    // 2. Grade Switching
    this.btnGrade1.addEventListener('click', () => this.switchGrade(1));
    this.btnGrade2.addEventListener('click', () => this.switchGrade(2));

    // 3. Tab Switching
    this.tabButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const tab = e.currentTarget.dataset.tab;
        this.switchTab(tab);
      });
    });

    // 4. Sample Selector
    this.selectSample.addEventListener('change', (e) => {
      const val = e.target.value;
      if (val && TEST_SAMPLES[val]) {
        this.inputSource.value = TEST_SAMPLES[val];
        this.translateNow();
      }
    });

    // 5. File Upload
    this.fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        this.inputSource.value = evt.target.result;
        this.translateNow();
      };
      reader.readAsText(file);
    });

    // 6. Clear Button
    this.btnClear.addEventListener('click', () => {
      this.inputSource.value = '';
      this.translateNow();
      this.inputSource.focus();
    });

    // 7. TTS Speech Synthesis
    this.btnSpeak.addEventListener('click', () => {
      this.speakText(this.inputSource.value);
    });

    // 8. Zoom Controls
    this.btnZoomIn.addEventListener('click', () => this.adjustZoom(0.15));
    this.btnZoomOut.addEventListener('click', () => this.adjustZoom(-0.15));

    // 9. Copy Braille
    this.btnCopyBraille.addEventListener('click', () => this.copyBrailleToClipboard());

    // 10. Perkins Drawer Toggle
    this.btnPerkinsToggle.addEventListener('click', () => this.togglePerkinsDrawer());
    this.btnClosePerkins.addEventListener('click', () => this.togglePerkinsDrawer(false));

    // Perkins Screen Keys
    Object.entries(this.perkinsKeys).forEach(([dot, el]) => {
      el.addEventListener('click', () => {
        const active = this.perkinsKeyboard.toggleTouchDot(parseInt(dot, 10));
        el.classList.toggle('pressed', active);
        this.updatePerkinsVisuals(Array.from(this.perkinsKeyboard.activeDots));
      });
    });

    this.btnCommitTouch.addEventListener('click', () => {
      this.perkinsKeyboard.commitTouchChord();
      Object.values(this.perkinsKeys).forEach(el => el.classList.remove('pressed'));
      this.updatePerkinsVisuals([]);
    });

    this.keySpace.addEventListener('click', () => {
      this.insertBrailleCellAtCursor('\u2800');
    });

    // 11. Theme Switcher
    this.btnThemeToggle.addEventListener('click', () => this.cycleTheme());

    // 12. Page Setup Modal
    this.btnPageSetup.addEventListener('click', () => {
      this.cfgCellsPerLine.value = this.embosser.options.cellsPerLine;
      this.cfgLinesPerPage.value = this.embosser.options.linesPerPage;
      this.cfgPageNumberLoc.value = this.embosser.options.pageNumberLocation;
      this.modalPageSetup.style.display = 'flex';
    });

    this.btnCloseModal.addEventListener('click', () => {
      this.modalPageSetup.style.display = 'none';
    });

    this.btnSavePageSetup.addEventListener('click', () => {
      const c = parseInt(this.cfgCellsPerLine.value, 10) || 40;
      const l = parseInt(this.cfgLinesPerPage.value, 10) || 25;
      const loc = this.cfgPageNumberLoc.value;
      this.embosser.setPageConfig(c, l, loc);
      this.statusPaperSize.textContent = `${c} เซลล์ × ${l} บรรทัด`;
      this.modalPageSetup.style.display = 'none';
      this.renderPaginatedView();
    });

    // 13. Export Menu & Actions
    this.btnExportMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      this.exportDropdown.classList.toggle('show');
    });

    document.addEventListener('click', () => {
      this.exportDropdown.classList.remove('show');
    });

    this.exportBRF.addEventListener('click', () => this.downloadBRF());
    this.exportUnicodeTxt.addEventListener('click', () => this.downloadUnicodeTxt());
    this.exportPEF.addEventListener('click', () => this.downloadPEF());
    this.printBraille.addEventListener('click', () => window.print());
  }

  // --- Translation Pipeline ---

  translateNow() {
    const rawText = this.inputSource.value;
    const result = this.translator.translate(rawText);
    this.activeResult = result;

    // 1. Update source statistics
    const chars = rawText.length;
    const words = rawText.trim() ? rawText.trim().split(/\s+/).length : 0;
    const lines = rawText.split('\n').length;
    this.sourceStats.innerHTML = `<span>${chars.toLocaleString()} ตัวอักษร</span> • <span>${words.toLocaleString()} คำ</span> • <span>${lines.toLocaleString()} บรรทัด</span>`;

    // 2. Render active tab view
    this.renderUnicodeView(result.braille);
    this.renderInteractiveView(result.cells);
    this.renderSimBrailleView(result.braille);
    this.renderPaginatedView();

    // 3. Update status bar
    const brailleCount = result.stats.brailleCells;
    this.statusCellsTotal.textContent = `เซลล์เบรลล์: ${brailleCount.toLocaleString()} เซลล์`;
  }

  switchGrade(grade) {
    this.currentGrade = grade;
    this.translator.setGrade(grade);

    if (grade === 1) {
      this.btnGrade1.classList.add('active');
      this.btnGrade2.classList.remove('active');
      this.statusMode.textContent = 'โหมด: ระดับ 1 (ตัวเต็ม)';
    } else {
      this.btnGrade1.classList.remove('active');
      this.btnGrade2.classList.add('active');
      this.statusMode.textContent = 'โหมด: ระดับ 2 (อักษรย่อ พ.ศ. 2564)';
    }
    this.translateNow();
  }

  switchTab(tab) {
    this.currentTab = tab;
    this.tabButtons.forEach(btn => {
      const isSelected = btn.dataset.tab === tab;
      btn.classList.toggle('active', isSelected);
      btn.setAttribute('aria-selected', isSelected);
    });

    this.viewUnicode.classList.toggle('active', tab === 'unicode');
    this.viewInteractive.classList.toggle('active', tab === 'interactive');
    this.viewSimBraille.classList.toggle('active', tab === 'simbraille');
    this.viewPaginated.classList.toggle('active', tab === 'paginated');
  }

  // --- Renderers ---

  renderUnicodeView(brailleText) {
    this.outputUnicode.textContent = brailleText || '⠠⠤⠤⠤⠤ (ยังไม่มีข้อความ)';
  }

  renderInteractiveView(cells) {
    this.outputInteractive.innerHTML = '';
    if (!cells || cells.length === 0) {
      this.outputInteractive.innerHTML = '<span class="inspector-placeholder">ยังไม่มีข้อมูลเซลล์เบรลล์</span>';
      return;
    }

    const fragment = document.createDocumentFragment();

    cells.forEach((cell, idx) => {
      // Newlines in grid
      if (cell.type === 'newline') {
        const br = document.createElement('div');
        br.style.width = '100%';
        br.style.height = '6px';
        fragment.appendChild(br);
        return;
      }

      const card = document.createElement('div');
      card.className = 'cell-card';
      card.dataset.index = idx;

      // Dots extraction
      const dots = unicodeToDots(cell.braille);

      // Matrix
      const matrix = document.createElement('div');
      matrix.className = 'dot-matrix';

      // 6 positions ordered column-wise: 1, 4, 2, 5, 3, 6
      const dotOrder = [1, 4, 2, 5, 3, 6];
      dotOrder.forEach(pos => {
        const dotSpan = document.createElement('span');
        dotSpan.className = 'dot' + (dots.includes(pos) ? ' active' : '');
        matrix.appendChild(dotSpan);
      });

      // Label (Thai character / word)
      const label = document.createElement('span');
      label.className = 'cell-label';
      label.textContent = cell.char === ' ' ? 'วรรค' : cell.char;

      // Braille Glyph
      const glyph = document.createElement('span');
      glyph.className = 'cell-glyph';
      glyph.textContent = cell.braille;

      card.appendChild(matrix);
      card.appendChild(label);
      card.appendChild(glyph);

      // Click / Hover interaction
      card.addEventListener('mouseenter', () => this.inspectCell(cell, dots, card));
      card.addEventListener('click', () => this.inspectCell(cell, dots, card));

      fragment.appendChild(card);
    });

    this.outputInteractive.appendChild(fragment);
  }

  renderSimBrailleView(brailleText) {
    let asciiOut = '';
    for (const ch of brailleText) {
      if (ch === '\n' || ch === '\r') {
        asciiOut += ch;
      } else {
        asciiOut += UNICODE_TO_ASCII[ch] !== undefined ? UNICODE_TO_ASCII[ch] : ch;
      }
    }
    this.outputSimBraille.textContent = asciiOut || '(ไม่มีข้อความ ASCII)';
  }

  renderPaginatedView() {
    if (!this.activeResult) return;
    const paginated = this.embosser.paginate(this.activeResult.braille);
    this.outputPaginated.innerHTML = '';

    this.statusPagesTotal.textContent = `จำนวนหน้ากระดาษเบรลล์: ${paginated.totalPages} หน้า`;

    if (paginated.pages.length === 0) {
      this.outputPaginated.innerHTML = '<span class="inspector-placeholder">ไม่มีเนื้อหาสำหรับจัดหน้า</span>';
      return;
    }

    paginated.pages.forEach(p => {
      const sheet = document.createElement('div');
      sheet.className = 'braille-sheet';

      const meta = document.createElement('div');
      meta.className = 'sheet-header-meta';
      meta.innerHTML = `<span>หน้ากระดาษเบรลล์ที่ ${p.pageNumber}</span> <span>${this.embosser.options.cellsPerLine} เซลล์ × ${this.embosser.options.linesPerPage} บรรทัด</span>`;

      const content = document.createElement('div');
      content.textContent = p.lines.join('\n');

      sheet.appendChild(meta);
      sheet.appendChild(content);
      this.outputPaginated.appendChild(sheet);
    });
  }

  // --- Inspector ---

  inspectCell(cell, dots, cardElement) {
    if (this.selectedCard) {
      this.selectedCard.classList.remove('selected');
    }
    this.selectedCard = cardElement;
    if (cardElement) cardElement.classList.add('selected');

    const dotStr = dots.length > 0 ? dots.sort((a, b) => a - b).join('-') : 'ว่าง (Blank)';
    const hex = cell.braille.charCodeAt(0).toString(16).toUpperCase();
    const ascii = UNICODE_TO_ASCII[cell.braille] || ' ';

    let typeDesc = 'ทั่วไป';
    switch (cell.type) {
      case 'consonant': typeDesc = 'พยัญชนะไทย'; break;
      case 'vowel': typeDesc = 'สระ'; break;
      case 'tone': typeDesc = 'วรรณยุกต์ (กฎ 2564)'; break;
      case 'contraction_g2': typeDesc = 'คำย่อระดับ 2 (Grade 2)'; break;
      case 'root_g2': typeDesc = 'คำมูล 2 พยางค์ระดับ 2'; break;
      case 'digit': typeDesc = 'เลขอารบิก'; break;
      case 'digit_thai': typeDesc = 'เลขไทย'; break;
      case 'number_sign': typeDesc = 'เครื่องหมายนำเลข'; break;
      case 'punctuation': typeDesc = 'เครื่องหมายวรรคตอน'; break;
      case 'space': typeDesc = 'ช่องว่าง (Space)'; break;
    }

    this.inspectorContent.innerHTML = `
      <div class="inspector-tag">อักษร: <strong>${cell.char}</strong></div>
      <div class="inspector-tag">จุดนูน: <strong>จุด ${dotStr}</strong></div>
      <div class="inspector-tag">Unicode: <strong>U+${hex} (${cell.braille})</strong></div>
      <div class="inspector-tag">Braille ASCII: <strong>'${ascii}'</strong></div>
      <div class="inspector-tag">ประเภท: <strong>${typeDesc}</strong></div>
    `;
  }

  // --- Perkins Keyboard Integration ---

  togglePerkinsDrawer(force) {
    const isShowing = this.perkinsDrawer.style.display !== 'none';
    const show = force !== undefined ? force : !isShowing;

    if (show) {
      this.perkinsDrawer.style.display = 'block';
      this.btnPerkinsToggle.classList.add('active');
      this.perkinsKeyboard.enable();
    } else {
      this.perkinsDrawer.style.display = 'none';
      this.btnPerkinsToggle.classList.remove('active');
      this.perkinsKeyboard.disable();
    }
  }

  updatePerkinsVisuals(activeDots) {
    // 1. Update keys on screen
    for (let i = 1; i <= 6; i++) {
      if (this.perkinsKeys[i]) {
        this.perkinsKeys[i].classList.toggle('pressed', activeDots.includes(i));
      }
    }

    // 2. Update live chord mini cell
    const cellDots = this.liveChordCell.querySelectorAll('.cell-dot');
    cellDots.forEach(d => {
      const pos = parseInt(d.dataset.pos, 10);
      d.classList.toggle('active', activeDots.includes(pos));
    });

    // 3. Update character glyph
    if (activeDots.length > 0) {
      const u = dotsToUnicode(activeDots);
      this.liveChordChar.textContent = u;
    } else {
      this.liveChordChar.textContent = '-';
    }
  }

  insertBrailleCellAtCursor(brailleChar) {
    // Reverse translate braille cell back to Thai or insert into textarea
    const backChar = this.translator.backTranslateCell(brailleChar);
    const toInsert = backChar !== undefined ? backChar : brailleChar;
    this.insertCharAtCursor(toInsert);
  }

  insertCharAtCursor(text) {
    const el = this.inputSource;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    el.value = el.value.substring(0, start) + text + el.value.substring(end);
    el.selectionStart = el.selectionEnd = start + text.length;
    this.translateNow();
  }

  deleteCharAtCursor() {
    const el = this.inputSource;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    if (start === end && start > 0) {
      el.value = el.value.substring(0, start - 1) + el.value.substring(end);
      el.selectionStart = el.selectionEnd = start - 1;
    } else if (start !== end) {
      el.value = el.value.substring(0, start) + el.value.substring(end);
      el.selectionStart = el.selectionEnd = start;
    }
    this.translateNow();
  }

  // --- Zoom & Theme Controls ---

  adjustZoom(delta) {
    this.brailleScale = Math.min(2.0, Math.max(0.6, this.brailleScale + delta));
    document.documentElement.style.setProperty('--braille-scale', this.brailleScale);
    this.zoomLevel.textContent = `${Math.round(this.brailleScale * 100)}%`;
  }

  cycleTheme() {
    const themes = ['dark', 'light', 'high-contrast'];
    const next = themes[(themes.indexOf(this.currentTheme) + 1) % themes.length];
    this.applyTheme(next);
  }

  applyTheme(theme) {
    this.currentTheme = theme;
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('tbtw_theme', theme);
  }

  // --- Exports & Downloads ---

  downloadBRF() {
    if (!this.activeResult) return;
    const paginated = this.embosser.paginate(this.activeResult.braille);
    const brfData = this.embosser.generateBRF(paginated);
    this.triggerDownload(brfData, 'tbtw_document.brf', 'text/plain;charset=us-ascii');
  }

  downloadUnicodeTxt() {
    if (!this.activeResult) return;
    this.triggerDownload(this.activeResult.braille, 'tbtw_braille_unicode.txt', 'text/plain;charset=utf-8');
  }

  downloadPEF() {
    if (!this.activeResult) return;
    const paginated = this.embosser.paginate(this.activeResult.braille);
    const pefData = this.embosser.generatePEF(paginated, { title: 'TBTW Modern Document' });
    this.triggerDownload(pefData, 'tbtw_document.pef', 'application/xml;charset=utf-8');
  }

  triggerDownload(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  copyBrailleToClipboard() {
    if (!this.activeResult || !this.activeResult.braille) return;
    navigator.clipboard.writeText(this.activeResult.braille).then(() => {
      const originalText = this.btnCopyBraille.textContent;
      this.btnCopyBraille.textContent = 'คัดลอกแล้ว!';
      this.btnCopyBraille.style.background = 'var(--accent-emerald)';
      setTimeout(() => {
        this.btnCopyBraille.textContent = originalText;
        this.btnCopyBraille.style.background = '';
      }, 1500);
    });
  }

  speakText(text) {
    if (!('speechSynthesis' in window) || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'th-TH';
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
  }
}

// Instantiate on DOMContentLoaded
window.addEventListener('DOMContentLoaded', () => {
  window.tbtwApp = new TBTWApp();
});
