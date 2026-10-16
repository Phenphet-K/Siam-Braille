/**
 * TBTW Modern - Thai Braille Translation Engine (มาตรฐาน พ.ศ. 2564)
 * พัฒนาต่อยอดจาก TBTW2 และ คู่มือมาตรฐานการใช้อักษรเบรลล์ในประเทศไทย
 */

import {
  THAI_CONSONANTS,
  THAI_VOWELS,
  COMPLEX_VOWELS,
  THAI_TONES,
  NUMBER_SIGN,
  THAI_NUMBER_SIGN,
  DIGIT_BRAILLE,
  THAI_DIGIT_MAP,
  PUNCTUATION_MAP,
  LEADING_VOWELS,
  POST_TONE_VOWELS,
  UNICODE_TO_ASCII,
  BRAILLE_ASCII_MAP,
  unicodeToDots
} from './braille-core.js';

import {
  PREFIX_CONTRACTIONS,
  E_TAIKHU_CONTRACTIONS,
  TWO_SYLLABLE_ROOTS,
  SHORT_WORD_CONTRACTIONS,
  PHRASE_CONTRACTIONS,
  EXCEPTION_DICTIONARY
} from './braille-grade2.js';

export class ThaiBrailleTranslator {
  constructor(options = {}) {
    this.options = {
      grade: options.grade || 1, // 1 = Grade 1 (ตัวเต็ม), 2 = Grade 2 (ตัวย่อ)
      includeCapitalSigns: options.includeCapitalSigns !== false,
      thaiNumberSign: options.thaiNumberSign !== false,
      ...options
    };
  }

  setGrade(grade) {
    this.options.grade = parseInt(grade, 10);
  }

  /**
   * แปลงข้อความภาษาไทย/อังกฤษเป็น Unicode Braille
   */
  translate(text) {
    if (!text) return { braille: '', cells: [], stats: { chars: 0, brailleCells: 0, words: 0 } };

    if (this.options.grade === 2) {
      return this.translateGrade2(text);
    }
    return this.translateGrade1(text);
  }

  /**
   * การแปลระดับ 1 (ตัวเต็มตามคู่มือ 2564)
   */
  translateGrade1(text) {
    let result = '';
    const cellMap = []; // เก็บ mapping แต่ละอักขระกับ Braille cells เพื่อนำไปทำ Interactive Inspector

    let i = 0;
    let inArabicNumber = false;
    let inThaiNumber = false;

    while (i < text.length) {
      const char = text[i];

      // 1. ตรวจสอบช่องว่างและการขึ้นบรรทัดใหม่
      if (char === ' ') {
        result += '\u2800';
        cellMap.push({ char: ' ', braille: '\u2800', type: 'space', index: i });
        inArabicNumber = false;
        inThaiNumber = false;
        i++;
        continue;
      }
      if (char === '\n' || char === '\r') {
        result += char;
        cellMap.push({ char: char, braille: char, type: 'newline', index: i });
        inArabicNumber = false;
        inThaiNumber = false;
        i++;
        continue;
      }

      // 2. ตัวเลขอารบิก
      if (/[0-9]/.test(char)) {
        if (!inArabicNumber) {
          result += NUMBER_SIGN;
          cellMap.push({ char: '[num]', braille: NUMBER_SIGN, type: 'number_sign', index: i });
          inArabicNumber = true;
        }
        const bDigit = DIGIT_BRAILLE[char]?.unicode || '\u2800';
        result += bDigit;
        cellMap.push({ char: char, braille: bDigit, type: 'digit', index: i });
        i++;
        continue;
      } else if (char === ',' && inArabicNumber && i + 1 < text.length && /[0-9]/.test(text[i + 1])) {
        // จุลภาคคั่นตัวเลข: จุด 2 (⠂) ตามคู่มือ 2564 หน้า 6 ข้อ 3.2
        result += '\u2802';
        cellMap.push({ char: ',', braille: '\u2802', type: 'punctuation', index: i });
        i++;
        continue;
      } else if (char === '.' && inArabicNumber && i + 1 < text.length && /[0-9]/.test(text[i + 1])) {
        // จุดทศนิยมในตัวเลข: จุด 2-5-6 (⠲) ตามคู่มือ 2564 หน้า 11
        result += '\u2832';
        cellMap.push({ char: '.', braille: '\u2832', type: 'punctuation', index: i });
        i++;
        continue;
      } else {
        inArabicNumber = false;
      }

      // 3. ตัวเลขไทย
      if (/[๑-๙๐]/.test(char)) {
        if (!inThaiNumber) {
          result += THAI_NUMBER_SIGN;
          cellMap.push({ char: '[th_num]', braille: THAI_NUMBER_SIGN, type: 'number_sign', index: i });
          inThaiNumber = true;
        }
        const mapped = THAI_DIGIT_MAP[char];
        const bDigit = DIGIT_BRAILLE[mapped]?.unicode || '\u2800';
        result += bDigit;
        cellMap.push({ char: char, braille: bDigit, type: 'digit_thai', index: i });
        i++;
        continue;
      } else {
        inThaiNumber = false;
      }

      // 4. เครื่องหมายวรรคตอนพิเศษ (ไปยาลใหญ่ ฯลฯ และ ไปยาลน้อย ฯ และ ไม้ยมก ๆ)
      if (text.substr(i, 5) === 'ฯลฯ') {
        const bPunc = THAI_TONES['ฯลฯ'].unicode;
        result += bPunc;
        cellMap.push({ char: 'ฯลฯ', braille: bPunc, type: 'punctuation', index: i });
        i += 5;
        continue;
      }
      if (char === 'ฯ') {
        const bPunc = THAI_TONES['ฯ'].unicode;
        result += bPunc;
        cellMap.push({ char: 'ฯ', braille: bPunc, type: 'punctuation', index: i });
        i++;
        continue;
      }
      if (char === 'ๆ') {
        const bPunc = THAI_TONES['ๆ'].unicode;
        result += bPunc;
        cellMap.push({ char: 'ๆ', braille: bPunc, type: 'tone', index: i });
        i++;
        continue;
      }

      // จุดกำกับคำย่อ (พ.ศ., ม., น.) vs จบประโยค (คู่มือ 2564 หน้า 6 ข้อ 3.1)
      if (char === '.') {
        const isAbbreviation = i > 0 && /[ก-ฮ]/.test(text[i - 1]);
        const bDot = isAbbreviation ? '\u2832' : '\u2838\u2832'; // ⠲ หรือ ⠸⠲
        result += bDot;
        cellMap.push({ char: '.', braille: bDot, type: 'punctuation', index: i });
        i++;
        continue;
      }

      // 5. เครื่องหมายวรรคตอนทั่วไป
      if (PUNCTUATION_MAP[char]) {
        const bPunc = PUNCTUATION_MAP[char];
        result += bPunc;
        cellMap.push({ char: char, braille: bPunc, type: 'punctuation', index: i });
        i++;
        continue;
      }

      // 6. อักษรละติน (ภาษาอังกฤษ)
      if (/[A-Za-z]/.test(char)) {
        const isUpper = char === char.toUpperCase() && char !== char.toLowerCase();
        if (isUpper && this.options.includeCapitalSigns) {
          result += '\u2820'; // จุด 6 สำหรับอักษรพิมพ์ใหญ่
          cellMap.push({ char: '[cap]', braille: '\u2820', type: 'capital_sign', index: i });
        }
        const bEng = BRAILLE_ASCII_MAP[char.toLowerCase()] || '\u2800';
        result += bEng;
        cellMap.push({ char: char, braille: bEng, type: 'english', index: i });
        i++;
        continue;
      }

      // 7. พยางค์และโครงสร้างภาษาไทย (Thai Syllable Cluster)
      const cluster = this.parseThaiCluster(text, i);
      if (cluster) {
        const clusterBraille = this.renderClusterGrade1(cluster);
        result += clusterBraille.braille;
        cellMap.push(...clusterBraille.cells);
        i = cluster.endIndex;
        continue;
      }

      // หากเป็นอักขระเดี่ยวที่ยังไม่ได้แปลง
      const singleBraille = this.translateSingleThaiChar(char);
      if (singleBraille) {
        result += singleBraille;
        cellMap.push({ char: char, braille: singleBraille, type: 'thai_single', index: i });
      } else {
        // อักขระที่ไม่รู้จัก
        result += char;
        cellMap.push({ char: char, braille: char, type: 'unknown', index: i });
      }
      i++;
    }

    return {
      braille: result,
      ascii: this.toBrailleAscii(result),
      cells: cellMap,
      stats: this.calculateStats(text, result)
    };
  }

  /**
   * การแปลระดับ 2 (ตัวย่อตามคู่มือ 2564 + ฐานข้อมูล TBTW)
   */
  translateGrade2(text) {
    let result = '';
    const cellMap = [];
    let i = 0;

    // รวบรวมตารางคำย่อยาวและคำย่อสั้น
    // เรียงตามความยาวเพื่อทำ Longest Match ก่อน
    const phraseEntries = Object.entries(PHRASE_CONTRACTIONS)
      .sort((a, b) => b[0].length - a[0].length);

    const shortEntries = Object.entries(SHORT_WORD_CONTRACTIONS)
      .sort((a, b) => b[0].length - a[0].length);

    const twoSylEntries = Object.entries(TWO_SYLLABLE_ROOTS)
      .sort((a, b) => b[0].length - a[0].length);

    while (i < text.length) {
      // 0. ช่องว่างและการขึ้นบรรทัดใหม่
      if (text[i] === ' ') {
        result += '\u2800';
        cellMap.push({ char: ' ', braille: '\u2800', type: 'space', index: i });
        i++;
        continue;
      }
      if (text[i] === '\n' || text[i] === '\r') {
        result += text[i];
        cellMap.push({ char: text[i], braille: text[i], type: 'newline', index: i });
        i++;
        continue;
      }

      // เครื่องหมายวรรคตอนพิเศษ
      if (text.substr(i, 5) === 'ฯลฯ') {
        result += '\u2830\u2807';
        cellMap.push({ char: 'ฯลฯ', braille: '\u2830\u2807', type: 'punctuation', index: i });
        i += 5;
        continue;
      }
      if (text[i] === 'ฯ') {
        result += '\u2830\u2806';
        cellMap.push({ char: 'ฯ', braille: '\u2830\u2806', type: 'punctuation', index: i });
        i++;
        continue;
      }
      if (text[i] === 'ๆ') {
        result += '\u2802';
        cellMap.push({ char: 'ๆ', braille: '\u2802', type: 'tone', index: i });
        i++;
        continue;
      }
      if (text[i] === '.') {
        const isAbbr = i > 0 && /[ก-ฮ]/.test(text[i - 1]);
        const bDot = isAbbr ? '\u2832' : '\u2838\u2832';
        result += bDot;
        cellMap.push({ char: '.', braille: bDot, type: 'punctuation', index: i });
        i++;
        continue;
      }

      // 1. ตรวจสอบข้อยกเว้นที่ไม่ต้องย่อ (Exception Dictionary)
      let isException = false;
      for (const [excWord, excConfig] of Object.entries(EXCEPTION_DICTIONARY)) {
        if (text.startsWith(excWord, i)) {
          if (excConfig.action === 'no_contraction') {
            // แปลแบบตัวเต็ม (Grade 1)
            const g1 = this.translateGrade1(excWord);
            result += g1.braille;
            cellMap.push(...g1.cells.map(c => ({ ...c, index: c.index + i })));
            i += excWord.length;
            isException = true;
            break;
          }
        }
      }
      if (isException) continue;

      // 2. ตรวจสอบกลุ่มคำ/วลียาว (CH78)
      let matchedPhrase = false;
      for (const [phrase, brl] of phraseEntries) {
        if (text.startsWith(phrase, i)) {
          result += brl;
          cellMap.push({ char: phrase, braille: brl, type: 'phrase_contraction', index: i });
          i += phrase.length;
          matchedPhrase = true;
          break;
        }
      }
      if (matchedPhrase) continue;

      // 3. ตรวจสอบคำมูล 2 พยางค์ (คู่มือ 2564 ข้อ 2.2 เช่น ค-ส, ป-ช, ธ-ช)
      let matchedTwoSyl = false;
      for (const [word, abbr] of twoSylEntries) {
        if (text.startsWith(word, i)) {
          // คำย่อ 2 พยางค์ เช่น ค-ส คือ ค + จุด 3-6 (⠤) + ส
          const parts = abbr.split('-');
          const c1 = THAI_CONSONANTS[parts[0]]?.unicode || '';
          const dash = '\u2824'; // จุด 3-6
          const c2 = THAI_CONSONANTS[parts[1]]?.unicode || '';
          const brl = c1 + dash + c2;
          result += brl;
          cellMap.push({ char: word, braille: brl, type: 'twosyl_contraction', index: i });
          i += word.length;
          matchedTwoSyl = true;
          break;
        }
      }
      if (matchedTwoSyl) continue;

      // 4. คำที่ใช้สระเอ ไม้ไต่คู้ และตัวสะกด (คู่มือ 2564 ข้อ 1.1.2)
      let matchedETaikhu = false;
      for (const [word, brl] of Object.entries(E_TAIKHU_CONTRACTIONS)) {
        if (text.startsWith(word, i)) {
          result += brl;
          cellMap.push({ char: word, braille: brl, type: 'etaikhu_contraction', index: i });
          i += word.length;
          matchedETaikhu = true;
          break;
        }
      }
      if (matchedETaikhu) continue;

      // 5. ตรวจสอบคำสั้น/พยางค์ย่อ (CH46 เช่น กระ=g-, ประ=&-, ความ=u-)
      let matchedShort = false;
      for (const [shortWord, brl] of shortEntries) {
        if (text.startsWith(shortWord, i)) {
          result += brl;
          cellMap.push({ char: shortWord, braille: brl, type: 'short_contraction', index: i });
          i += shortWord.length;
          matchedShort = true;
          break;
        }
      }
      if (matchedShort) continue;

      // 6. ตรวจสอบจุดย่อนำหน้าพยัญชนะต้น (Prefix Contraction: -าง, -ัง, -าน, -ัน, -าย, -อง)
      // เช่น ทาง = จุด 4-6 + ท, นั่ง = จุด 4-5-6 + น + ไม้โท
      let matchedPrefix = false;
      for (const rule of PREFIX_CONTRACTIONS) {
        const remaining = text.slice(i);
        rule.pattern.lastIndex = 0;
        const match = rule.pattern.exec(remaining);
        if (match && match.index === 0) {
          const consonant = match[1];
          const tone = match[2];
          const fullMatch = match[0];

          // รูปแบบ: จุดย่อ + พยัญชนะ + วรรณยุกต์ (ถ้ามี)
          const cBrl = THAI_CONSONANTS[consonant]?.unicode || '';
          const tBrl = tone ? (THAI_TONES[tone]?.unicode || '') : '';
          const brl = rule.prefix + cBrl + tBrl;

          result += brl;
          cellMap.push({ char: fullMatch, braille: brl, type: 'prefix_contraction', index: i });
          i += fullMatch.length;
          matchedPrefix = true;
          break;
        }
      }
      if (matchedPrefix) continue;

      // 7. ตัวเลขอารบิก (เช่น 1,240 หรือ 250.50)
      if (/[0-9]/.test(text[i])) {
        const numMatch = text.slice(i).match(/^[0-9]+([,.][0-9]+)*/);
        if (numMatch) {
          const numStr = numMatch[0];
          const g1Num = this.translateGrade1(numStr);
          result += g1Num.braille;
          cellMap.push(...g1Num.cells.map(c => ({ ...c, index: c.index + i })));
          i += numStr.length;
          continue;
        }
      }

      // 8. ตัวเลขไทย (เช่น ๑๒๓ หรือ ๒๕๖๔)
      if (/[๑-๙๐]/.test(text[i])) {
        const numMatch = text.slice(i).match(/^[๑-๙๐]+/);
        if (numMatch) {
          const numStr = numMatch[0];
          const g1Num = this.translateGrade1(numStr);
          result += g1Num.braille;
          cellMap.push(...g1Num.cells.map(c => ({ ...c, index: c.index + i })));
          i += numStr.length;
          continue;
        }
      }

      // หากไม่ตรงกับคำย่อใดๆ ให้แปลงตามตัวเต็ม (Grade 1) ของพยางค์นั้น
      const cluster = this.parseThaiCluster(text, i);
      if (cluster) {
        const clusterBraille = this.renderClusterGrade1(cluster);
        result += clusterBraille.braille;
        cellMap.push(...clusterBraille.cells);
        i = cluster.endIndex;
        continue;
      }

      // ตัวเลข/วรรคตอน/ภาษาอังกฤษเดี่ยว
      const g1Single = this.translateGrade1(text[i]);
      result += g1Single.braille;
      cellMap.push(...g1Single.cells.map(c => ({ ...c, index: i })));
      i++;
    }

    return {
      braille: result,
      ascii: this.toBrailleAscii(result),
      cells: cellMap,
      stats: this.calculateStats(text, result)
    };
  }

  /**
   * วิเคราะห์กลุ่มพยางค์ภาษาไทย (Syllable Cluster Parser)
   * รองรับการจัดลำดับตามคู่มือ 2564 หน้า 7
   */
  parseThaiCluster(text, startIndex) {
    let i = startIndex;
    if (i >= text.length) return null;

    let leadingVowel = '';
    let consonants = [];
    let upperLowerVowel = '';
    let tone = '';
    let postToneVowel = '';
    let finalConsonant = '';
    let karan = false;

    // 1. ตรวจสอบสระหน้า (เ, แ, โ, ใ, ไ)
    if (LEADING_VOWELS.has(text[i])) {
      leadingVowel = text[i];
      i++;
      if (i >= text.length) {
        return { leadingVowel, consonants: [], endIndex: i };
      }
    }

    // 2. ตรวจสอบพยัญชนะต้น (ตัวแรก)
    if (/[ก-ฮ]/.test(text[i])) {
      consonants.push(text[i]);
      i++;

      // ตรวจสอบพยัญชนะควบกล้ำ/อักษรนำ (ตัวที่ 2 เช่น กร, ปร, คว, หน, หม)
      if (i < text.length && /[ก-ฮ]/.test(text[i])) {
        // หากตัวถัดไปไม่ใช่พยัญชนะตัวสุดท้ายหรือมีสระ/วรรณยุกต์ตามหลัง
        const nextChar = i + 1 < text.length ? text[i + 1] : '';
        if (/[รลวหนมย]/.test(text[i]) && (/[ะ-ู่-๋]/.test(nextChar) || nextChar === '')) {
          consonants.push(text[i]);
          i++;
        }
      }
    } else if (!leadingVowel) {
      return null;
    }

    // 3. ตรวจสอบสระบน/สระล่าง/ไม้หันอากาศ
    if (i < text.length && /[ะ-ูั็]/.test(text[i])) {
      upperLowerVowel = text[i];
      i++;
    }

    // 4. ตรวจสอบวรรณยุกต์
    if (i < text.length && /[่-๋]/.test(text[i])) {
      tone = text[i];
      i++;
    }

    // 5. ตรวจสอบสระหลังวรรณยุกต์ (ตามกฎคู่มือ 2564: -า, -อ, -ว วางหลังวรรณยุกต์)
    if (i < text.length && POST_TONE_VOWELS.has(text[i])) {
      postToneVowel = text[i];
      i++;
    }

    // 6. ตรวจสอบตัวการันต์ (-์)
    if (i < text.length && text[i] === '์') {
      karan = true;
      i++;
    }

    return {
      leadingVowel,
      consonants,
      upperLowerVowel,
      tone,
      postToneVowel,
      karan,
      startIndex,
      endIndex: i
    };
  }

  /**
   * เรนเดอร์กลุ่มพยางค์เป็น Braille Cells ตามกฎมาตรฐาน 2564
   */
  renderClusterGrade1(c) {
    let braille = '';
    const cells = [];

    // กฎ 1.1: สระหน้า (เ-, แ-, โ-, ใ-, ไ-) วางหน้าพยัญชนะ
    if (c.leadingVowel) {
      // ตรวจสอบสระผสมพิเศษ เช่น เ-ีย, เ-ือ, เ-อ, เ-า
      if (c.leadingVowel === 'เ' && c.postToneVowel === 'า') {
        // สระ เ-า
        const b = COMPLEX_VOWELS['เ-า'].unicode;
        // วาง เ- หน้าพยัญชนะ และ -า หลังพยัญชนะ/วรรณยุกต์
      }
      const bVowel = THAI_VOWELS[c.leadingVowel]?.unicode || '';
      braille += bVowel;
      cells.push({ char: c.leadingVowel, braille: bVowel, type: 'leading_vowel' });
    }

    // กฎ: พยัญชนะต้น
    for (const cons of c.consonants) {
      const bCons = THAI_CONSONANTS[cons]?.unicode || '';
      braille += bCons;
      cells.push({ char: cons, braille: bCons, type: 'consonant' });
    }

    // กฎ 1.2: สระบน/ล่าง (สระ -ะ, -ิ, -ี, -ึ, -ื, -ุ, -ู, -ั) วางไว้หลังพยัญชนะ
    if (c.upperLowerVowel) {
      const bVowel = THAI_VOWELS[c.upperLowerVowel]?.unicode || '';
      braille += bVowel;
      cells.push({ char: c.upperLowerVowel, braille: bVowel, type: 'vowel' });
    }

    // วรรณยุกต์ (ไม้เอก, โท, ตรี, จัตวา)
    if (c.tone) {
      const bTone = THAI_TONES[c.tone]?.unicode || '';
      braille += bTone;
      cells.push({ char: c.tone, braille: bTone, type: 'tone' });
    }

    // กฎ 1.3: สระ -า, -อ, และ -ว วางไว้หลังวรรณยุกต์ (เช่น บ้าน = บ + ้ + า + น)
    if (c.postToneVowel) {
      const bVowel = THAI_VOWELS[c.postToneVowel]?.unicode || (THAI_CONSONANTS[c.postToneVowel]?.unicode || '');
      braille += bVowel;
      cells.push({ char: c.postToneVowel, braille: bVowel, type: 'post_tone_vowel' });
    }

    // ทัณฑฆาต (การันต์)
    if (c.karan) {
      const bKaran = THAI_TONES['์'].unicode;
      braille += bKaran;
      cells.push({ char: '์', braille: bKaran, type: 'karan' });
    }

    return { braille, cells };
  }

  translateSingleThaiChar(char) {
    if (THAI_CONSONANTS[char]) return THAI_CONSONANTS[char].unicode;
    if (THAI_VOWELS[char]) return THAI_VOWELS[char].unicode;
    if (THAI_TONES[char]) return THAI_TONES[char].unicode;
    return null;
  }

  /**
   * แปลง Unicode Braille เป็น Braille ASCII (สำหรับเครื่องพิมพ์ Embosser)
   */
  toBrailleAscii(unicodeBraille) {
    let ascii = '';
    for (const ch of unicodeBraille) {
      if (UNICODE_TO_ASCII[ch]) {
        ascii += UNICODE_TO_ASCII[ch];
      } else if (ch === '\n' || ch === '\r' || ch === '\t') {
        ascii += ch;
      } else {
        ascii += ' ';
      }
    }
    return ascii;
  }

  /**
   * แปลงกลับจาก Unicode Braille เป็นข้อความภาษาไทย (Back-translation)
   */
  backTranslate(brailleText) {
    // ตารางย้อนกลับพยัญชนะ
    const reverseConsonants = {};
    for (const [k, v] of Object.entries(THAI_CONSONANTS)) {
      reverseConsonants[v.unicode] = k;
    }

    // ตารางย้อนกลับสระ
    const reverseVowels = {};
    for (const [k, v] of Object.entries(THAI_VOWELS)) {
      reverseVowels[v.unicode] = k;
    }

    // ตารางย้อนกลับวรรณยุกต์
    const reverseTones = {};
    for (const [k, v] of Object.entries(THAI_TONES)) {
      reverseTones[v.unicode] = k;
    }

    let out = '';
    let i = 0;
    let isNum = false;

    while (i < brailleText.length) {
      const ch = brailleText[i];
      if (ch === '\u2800' || ch === ' ') {
        out += ' ';
        isNum = false;
        i++;
        continue;
      }
      if (ch === '\n' || ch === '\r') {
        out += ch;
        isNum = false;
        i++;
        continue;
      }
      if (ch === NUMBER_SIGN) {
        isNum = true;
        i++;
        continue;
      }

      if (isNum) {
        let foundDigit = false;
        for (const [digit, info] of Object.entries(DIGIT_BRAILLE)) {
          if (info.unicode === ch) {
            out += digit;
            foundDigit = true;
            break;
          }
        }
        if (foundDigit) {
          i++;
          continue;
        } else {
          isNum = false;
        }
      }

      // ตรวจสอบแบบ 2 เซลล์ก่อน
      if (i + 1 < brailleText.length) {
        const twoCell = ch + brailleText[i + 1];
        if (reverseConsonants[twoCell]) {
          out += reverseConsonants[twoCell];
          i += 2;
          continue;
        }
      }

      if (reverseConsonants[ch]) {
        out += reverseConsonants[ch];
      } else if (reverseVowels[ch]) {
        out += reverseVowels[ch];
      } else if (reverseTones[ch]) {
        out += reverseTones[ch];
      } else {
        out += ch;
      }
      i++;
    }

    return out;
  }

  calculateStats(original, braille) {
    const chars = original.length;
    const brailleCells = [...braille].filter(c => c >= '\u2800' && c <= '\u28FF').length;
    const words = original.trim().split(/\s+/).filter(Boolean).length;
    return { chars, brailleCells, words };
  }
}
