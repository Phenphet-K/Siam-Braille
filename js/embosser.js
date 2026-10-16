/**
 * TBTW Modern - Braille Embosser & Page Formatter
 * จัดหน้ากระดาษและส่งออกไฟล์พิมพ์เบรลล์ (.BRF, .PEF, .TXT)
 */

import { NUMBER_SIGN, DIGIT_BRAILLE, UNICODE_TO_ASCII } from './braille-core.js';

export class BrailleEmbosser {
  constructor(options = {}) {
    this.options = {
      cellsPerLine: options.cellsPerLine || 40,   // จำนวนเซลล์ต่อบรรทัด (มาตรฐาน 30 - 40 เซลล์)
      linesPerPage: options.linesPerPage || 25,   // จำนวนบรรทัดต่อหน้า (มาตรฐาน 25 - 28 บรรทัด)
      pageNumberLocation: options.pageNumberLocation || 'top-right', // 'top-right', 'top-left', 'bottom-right', 'none'
      interpoint: options.interpoint || false,    // พิมพ์สองหน้า (Double-sided)
      ...options
    };
  }

  setPageConfig(cellsPerLine, linesPerPage, pageNumberLocation) {
    if (cellsPerLine) this.options.cellsPerLine = parseInt(cellsPerLine, 10);
    if (linesPerPage) this.options.linesPerPage = parseInt(linesPerPage, 10);
    if (pageNumberLocation) this.options.pageNumberLocation = pageNumberLocation;
  }

  /**
   * จัดรูปแบบข้อความเบรลล์เป็นหน้าและบรรทัด (Pagination & Word Wrap)
   */
  paginate(brailleText) {
    const cellsPerLine = this.options.cellsPerLine;
    const linesPerPage = this.options.linesPerPage;
    const loc = this.options.pageNumberLocation;

    // แยกย่อหน้าตาม Newlines
    const rawParagraphs = brailleText.split(/\r?\n/);
    const formattedLines = [];

    for (const para of rawParagraphs) {
      if (para.length === 0) {
        formattedLines.push('');
        continue;
      }

      // Word wrapping บนอักษรเบรลล์
      // คำในเบรลล์คั่นด้วยช่องว่าง \u2800 หรือ space
      const words = para.split(/(\u2800|\s)/);
      let currentLine = '';

      for (const word of words) {
        if (!word) continue;

        if (currentLine.length + word.length <= cellsPerLine) {
          currentLine += word;
        } else {
          if (currentLine.length > 0) {
            formattedLines.push(currentLine.trimEnd());
            currentLine = '';
          }

          // หากคำยาวเกิน 1 บรรทัด ให้ตัดคำ
          let remaining = word;
          while (remaining.length > cellsPerLine) {
            formattedLines.push(remaining.slice(0, cellsPerLine));
            remaining = remaining.slice(cellsPerLine);
          }
          currentLine = remaining;
        }
      }

      if (currentLine.length > 0) {
        formattedLines.push(currentLine.trimEnd());
      }
    }

    // จัดกลุ่มบรรทัดเป็นหน้า (Pages)
    const pages = [];
    let pageNum = 1;
    let lineIdx = 0;

    // คำนวณเนื้อที่สำหรับเลขหน้า
    const bodyLinesPerPage = loc !== 'none' ? linesPerPage - 1 : linesPerPage;

    while (lineIdx < formattedLines.length || pages.length === 0) {
      const pageLines = [];
      const numBraille = this.formatPageNumber(pageNum);

      // หัวกระดาษ (ถ้ามีเลขหน้าบน)
      if (loc === 'top-right') {
        const padding = ' '.repeat(Math.max(0, cellsPerLine - numBraille.length));
        pageLines.push(padding + numBraille);
      } else if (loc === 'top-left') {
        pageLines.push(numBraille);
      }

      // เนื้อหาในหน้า
      for (let l = 0; l < bodyLinesPerPage && lineIdx < formattedLines.length; l++) {
        pageLines.push(formattedLines[lineIdx]);
        lineIdx++;
      }

      // ท้ายกระดาษ (ถ้ามีเลขหน้าล่าง)
      if (loc === 'bottom-right') {
        while (pageLines.length < linesPerPage - 1) {
          pageLines.push('');
        }
        const padding = ' '.repeat(Math.max(0, cellsPerLine - numBraille.length));
        pageLines.push(padding + numBraille);
      }

      pages.push({
        pageNumber: pageNum,
        lines: pageLines,
        text: pageLines.join('\n')
      });

      pageNum++;
      if (lineIdx >= formattedLines.length) break;
    }

    return {
      pages,
      totalPages: pages.length,
      totalLines: formattedLines.length,
      cellsPerLine,
      linesPerPage
    };
  }

  /**
   * แปลงเลขหน้าเป็นอักษรเบรลล์
   */
  formatPageNumber(num) {
    const s = String(num);
    let out = NUMBER_SIGN;
    for (const d of s) {
      out += DIGIT_BRAILLE[d]?.unicode || '';
    }
    return out;
  }

  /**
   * สร้างไฟล์ .BRF (Braille Ready Format) สำหรับส่งเข้าเครื่องพิมพ์เบรลล์
   * BRF ใช้ Braille ASCII และใช้ Form Feed (0x0C) คั่นระหว่างหน้า
   */
  generateBRF(paginated) {
    const brfPages = paginated.pages.map(p => {
      const asciiLines = p.lines.map(line => {
        let asciiLine = '';
        for (const ch of line) {
          asciiLine += UNICODE_TO_ASCII[ch] !== undefined ? UNICODE_TO_ASCII[ch] : ch;
        }
        return asciiLine;
      });
      return asciiLines.join('\r\n');
    });

    // Form Feed (\x0C) คั่นระหว่างหน้า
    return brfPages.join('\r\n\x0C\r\n');
  }

  /**
   * สร้างไฟล์ .PEF (Portable Embosser Format XML มาตรฐานสากล)
   */
  generatePEF(paginated, meta = {}) {
    const title = meta.title || 'TBTW Document';
    const date = new Date().toISOString().split('T')[0];

    const pagesXml = paginated.pages.map(p => {
      const rows = p.lines.map(l => `        <row>${escapeXml(l)}</row>`).join('\n');
      return `      <page>\n${rows}\n      </page>`;
    }).join('\n');

    return `<?xml version="1.0" encoding="UTF-8"?>
<pef version="2008-1" xmlns="http://www.daisy.org/ns/2008/pef">
  <head>
    <meta xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>${escapeXml(title)}</dc:title>
      <dc:format>application/x-pef+xml</dc:format>
      <dc:date>${date}</dc:date>
    </meta>
  </head>
  <body>
    <volume cols="${paginated.cellsPerLine}" rows="${paginated.linesPerPage}">
      <section>
${pagesXml}
      </section>
    </volume>
  </body>
</pef>`;
  }
}

function escapeXml(unsafe) {
  return unsafe.replace(/[<>&'"]/g, c => {
    switch (c) {
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '&': return '&amp;';
      case '\'': return '&apos;';
      case '"': return '&quot;';
    }
  });
}
