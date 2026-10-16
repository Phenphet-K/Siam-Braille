/**
 * TBTW Modern - Virtual 6-Key Perkins Brailler Keyboard
 * แป้นพิมพ์ 6 ปุ่มจำลองสำหรับผู้พิการทางสายตาและผู้เรียนอักษรเบรลล์
 * Key map: S(จุด3) D(จุด2) F(จุด1) | J(จุด4) K(จุด5) L(จุด6) | Spacebar(เคาะวรรค)
 */

import { dotsToUnicode } from './braille-core.js';

export class VirtualPerkinsKeyboard {
  constructor(options = {}) {
    this.onCellProduced = options.onCellProduced || (() => {});
    this.onBackspace = options.onBackspace || (() => {});
    this.onNewline = options.onNewline || (() => {});
    this.onChordChange = options.onChordChange || (() => {});

    this.activeDots = new Set();
    this.pressedKeys = new Set();
    this.isEnabled = false;
    this.chordTimeout = null;

    this.KEY_TO_DOT = {
      'f': 1, 'F': 1, // บนซ้าย
      'd': 2, 'D': 2, // กลางซ้าย
      's': 3, 'S': 3, // ล่างซ้าย
      'j': 4, 'J': 4, // บนขวา
      'k': 5, 'K': 5, // กลางขวา
      'l': 6, 'L': 6, // ล่างขวา
    };

    this.handleKeyDown = this.handleKeyDown.bind(this);
    this.handleKeyUp = this.handleKeyUp.bind(this);
  }

  enable() {
    if (this.isEnabled) return;
    this.isEnabled = true;
    if (typeof window !== 'undefined') {
      window.addEventListener('keydown', this.handleKeyDown);
      window.addEventListener('keyup', this.handleKeyUp);
    }
  }

  disable() {
    if (!this.isEnabled) return;
    this.isEnabled = false;
    if (typeof window !== 'undefined') {
      window.removeEventListener('keydown', this.handleKeyDown);
      window.removeEventListener('keyup', this.handleKeyUp);
    }
    this.activeDots.clear();
    this.pressedKeys.clear();
  }

  handleKeyDown(e) {
    if (!this.isEnabled) return;

    // ถ้ากดปุ่ม Space
    if (e.code === 'Space') {
      e.preventDefault();
      this.produceCell([]); // Blank cell
      return;
    }

    // ถ้ากดปุ่ม Backspace
    if (e.code === 'Backspace') {
      e.preventDefault();
      this.onBackspace();
      return;
    }

    // ถ้ากดปุ่ม Enter
    if (e.code === 'Enter') {
      e.preventDefault();
      this.onNewline();
      return;
    }

    const dot = this.KEY_TO_DOT[e.key];
    if (dot !== undefined) {
      e.preventDefault();
      this.activeDots.add(dot);
      this.pressedKeys.add(e.key.toLowerCase());
      this.onChordChange(Array.from(this.activeDots));
    }
  }

  handleKeyUp(e) {
    if (!this.isEnabled) return;

    const dot = this.KEY_TO_DOT[e.key];
    if (dot !== undefined) {
      this.pressedKeys.delete(e.key.toLowerCase());

      // เมื่อปล่อยปุ่มทั้งหมดของคอร์ด (Chord Release) ให้ปล่อยตัวอักษร 1 เซลล์
      if (this.pressedKeys.size === 0 && this.activeDots.size > 0) {
        const dots = Array.from(this.activeDots).sort((a, b) => a - b);
        this.produceCell(dots);
        this.activeDots.clear();
        this.onChordChange([]);
      }
    }
  }

  produceCell(dots) {
    const unicode = dotsToUnicode(dots);
    this.onCellProduced({
      dots,
      unicode,
      timestamp: Date.now()
    });
  }

  // กดจำลองผ่านปุ่มคลิกบนหน้าจอ (Touch / Mouse)
  toggleTouchDot(dotNum) {
    if (this.activeDots.has(dotNum)) {
      this.activeDots.delete(dotNum);
    } else {
      this.activeDots.add(dotNum);
    }
    this.onChordChange(Array.from(this.activeDots));
  }

  commitTouchChord() {
    if (this.activeDots.size > 0) {
      const dots = Array.from(this.activeDots).sort((a, b) => a - b);
      this.produceCell(dots);
      this.activeDots.clear();
      this.onChordChange([]);
    }
  }
}
