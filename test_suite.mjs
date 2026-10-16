/**
 * TBTW Modern - Comprehensive Test Suite
 * ทดสอบความถูกต้องของระบบแปลเบรลล์ตามคู่มือมาตรฐาน พ.ศ. 2564
 */

import { ThaiBrailleTranslator } from './js/translator.js';
import { BrailleEmbosser } from './js/embosser.js';
import { VirtualPerkinsKeyboard } from './js/virtual-keyboard.js';
import { unicodeToDots, dotsToUnicode, UNICODE_TO_ASCII } from './js/braille-core.js';

console.log('================================================================');
console.log('🚀 TBTW Modern - Unit & Integration Test Suite (มาตรฐาน 2564)');
console.log('================================================================\n');

let passedTests = 0;
let totalTests = 0;

function assert(description, actual, expected) {
  totalTests++;
  const match = actual === expected;
  if (match) {
    passedTests++;
    console.log(`  ✅ [PASS] ${description}`);
  } else {
    console.error(`  ❌ [FAIL] ${description}`);
    console.error(`     Expected: ${expected}`);
    console.error(`     Actual:   ${actual}`);
  }
}

// 1. Core Consonants & Dot Mapping Tests
console.log('📌 Test Group 1: 44 พยัญชนะไทยและการแมปจุด');
assert('ก (จุด 1-2-4-5) -> ⠛', dotsToUnicode([1, 2, 4, 5]), '\u281B');
assert('ข (จุด 1-3) -> ⠅', dotsToUnicode([1, 3]), '\u2805');
assert('ง (จุด 3-4-5) -> ⠜', dotsToUnicode([3, 4, 5]), '\u281C');
assert('จ (จุด 2-4-5) -> ⠚', dotsToUnicode([2, 4, 5]), '\u281A');
assert('บ (จุด 1-2) -> ⠃', dotsToUnicode([1, 2]), '\u2803');
assert('ป (จุด 1-2-3-4) -> ⠏', dotsToUnicode([1, 2, 3, 4]), '\u280F');
assert('ม (จุด 1-3-4) -> ⠍', dotsToUnicode([1, 3, 4]), '\u280D');
assert('ย (จุด 1-3-4-5-6) -> ⠽', dotsToUnicode([1, 3, 4, 5, 6]), '\u283D');
assert('ร (จุด 1-2-3-5) -> ⠗', dotsToUnicode([1, 2, 3, 5]), '\u2817');
assert('ล (จุด 1-2-3) -> ⠇', dotsToUnicode([1, 2, 3]), '\u2807');
assert('ว (จุด 2-4-5-6) -> ⠺', dotsToUnicode([2, 4, 5, 6]), '\u283A');
assert('ส (จุด 2-3-4) -> ⠎', dotsToUnicode([2, 3, 4]), '\u280E');
assert('ห (จุด 1-2-5) -> ⠓', dotsToUnicode([1, 2, 5]), '\u2813');
assert('อ (จุด 1-3-5) -> ⠕', dotsToUnicode([1, 3, 5]), '\u2815');
assert('ฮ (จุด 1-2-3-4-5-6) -> ⠿', dotsToUnicode([1, 2, 3, 4, 5, 6]), '\u283F');

// 2. Grade 1 Ordering Rules (Post-tone vowels vs Leading vowels)
console.log('\n📌 Test Group 2: ลำดับการเรียงสระและวรรณยุกต์ (คู่มือ หน้า 7)');
const tGrade1 = new ThaiBrailleTranslator({ grade: 1 });

// บ้าน: บ + ไม้โท (⠲) + า (⠡) + น (⠝) -> ⠃⠲⠡⠝
assert('บ้าน (สระ า วางหลังวรรณยุกต์)', tGrade1.translate('บ้าน').braille, '⠃⠲⠡⠝');

// พ่อ: พ (⠟) + ไม้เอก (⠔) + อ (⠕) -> ⠟⠔⠕
assert('พ่อ (สระ อ วางหลังวรรณยุกต์)', tGrade1.translate('พ่อ').braille, '⠟⠔⠕');

// เวลา: เ (⠋) + ว (⠺) + ล (⠇) + า (⠡) -> ⠋⠺⠇⠡
assert('เวลา (สระหน้า เ วางก่อนพยัญชนะ)', tGrade1.translate('เวลา').braille, '⠋⠺⠇⠡');

// 3. Numbers & Numeric Punctuation (คู่มือ หน้า 6, 10, 11)
console.log('\n📌 Test Group 3: การเขียนตัวเลขและวรรคตอนในตัวเลข');
// 1,240 -> ⠼⠁⠂⠃⠙⠚
assert('1,240 (เลขอารบิก + จุลภาคจุด 2)', tGrade1.translate('1,240').braille, '⠼⠁⠂⠃⠙⠚');

// 25.6 -> ⠼⠃⠑⠲⠋
assert('25.6 (ทศนิยม จุด 2-5-6)', tGrade1.translate('25.6').braille, '⠼⠃⠑⠲⠋');

// ๑๒๓ -> ⠠⠼⠁⠃⠉
assert('๑๒๓ (เลขไทย จุด 6 + 3-4-5-6)', tGrade1.translate('๑๒๓').braille, '⠠⠼⠁⠃⠉');

// พ.ศ. -> ⠟⠲⠸⠯⠲
assert('พ.ศ. (จุดคำย่อ จุด 2-5-6)', tGrade1.translate('พ.ศ.').braille, '⠟⠲⠸⠯⠲');

// 4. Special Punctuation (คู่มือ หน้า 7-8)
console.log('\n📌 Test Group 4: เครื่องหมายวรรคตอนพิเศษ');
assert('ฯลฯ (ไปยาลใหญ่ จุด 5-6 + 1-2-3) -> ⠰⠇', tGrade1.translate('ฯลฯ').braille, '⠰⠇');
assert('กรุงเทพฯ (ไปยาลน้อย จุด 5-6 + 2-3) -> ⠰⠆', tGrade1.translate('ฯ').braille, '⠰⠆');
assert('ๆ (ไม้ยมก จุด 2) -> ⠂', tGrade1.translate('ๆ').braille, '⠂');

// 5. Grade 2 Contractions (คู่มือ บทที่ 2)
console.log('\n📌 Test Group 5: การแปลระดับ 2 (อักษรย่อ)');
const tGrade2 = new ThaiBrailleTranslator({ grade: 2 });

// เด็ก -> ⠨⠛ (เ-็ก contraction)
assert('เด็ก (คำย่อ เ-็ก)', tGrade2.translate('เด็ก').braille, '⠨⠛');

// เก็บ -> ⠨⠃
assert('เก็บ (คำย่อ เ-็ก)', tGrade2.translate('เก็บ').braille, '⠨⠃');

// เห็น -> ⠈⠝
assert('เห็น (คำย่อ เ-็ก)', tGrade2.translate('เห็น').braille, '⠈⠝');

// บ้าน -> ⠘⠃⠲ (Prefix -าน + บ + ไม้โท)
assert('บ้าน (คำย่อ Prefix -าน)', tGrade2.translate('บ้าน').braille, '⠘⠃⠲');

// ต่างๆ -> ⠰⠡⠂ (Prefix -าง + ต + ไม้ยมก)
assert('ต่างๆ (คำย่อ Prefix -าง + ไม้ยมก)', tGrade2.translate('ต่างๆ').braille, '⠰⠡⠂');

// 6. Embosser & Pagination Tests
console.log('\n📌 Test Group 6: เครื่องพิมพ์เบรลล์และการจัดหน้ากระดาษ');
const embosser = new BrailleEmbosser({ cellsPerLine: 40, linesPerPage: 25 });
const longBraille = ('⠃⠲⠡⠝⠀'.repeat(60)); // 300 cells
const paginated = embosser.paginate(longBraille);
assert('จำนวนเซลล์ต่อบรรทัดไม่เกิน 40', paginated.pages[0].lines.every(l => l.length <= 40), true);
assert('สร้างหน้ามากกว่า 0', paginated.totalPages > 0, true);

// BRF Generator Test
const brf = embosser.generateBRF(paginated);
assert('BRF Output มีเนื้อหา', brf.length > 0, true);

// PEF XML Generator Test
const pef = embosser.generatePEF(paginated);
assert('PEF Output เป็น XML ที่ถูกต้อง', pef.includes('<?xml version="1.0"'), true);
assert('PEF มีแท็ก <volume>', pef.includes('<volume cols="40" rows="25">'), true);

// 7. Virtual Perkins Keyboard Chording Test
console.log('\n📌 Test Group 7: แป้นพิมพ์ 6 ปุ่ม Perkins Brailler');
let producedCell = null;
const perkins = new VirtualPerkinsKeyboard({
  onCellProduced: (c) => { producedCell = c; }
});
perkins.enable();

// Simulate chord [1, 2] -> 'บ' (⠃)
perkins.activeDots.add(1);
perkins.activeDots.add(2);
perkins.produceCell(Array.from(perkins.activeDots));
assert('Perkins คอร์ด [1, 2] ผลิตเซลล์ บ (⠃)', producedCell.unicode, '⠃');

// Simulate chord [1, 2, 4, 5] -> 'ก' (⠛)
perkins.activeDots.clear();
perkins.activeDots.add(1);
perkins.activeDots.add(2);
perkins.activeDots.add(4);
perkins.activeDots.add(5);
perkins.produceCell(Array.from(perkins.activeDots));
assert('Perkins คอร์ด [1, 2, 4, 5] ผลิตเซลล์ ก (⠛)', producedCell.unicode, '⠛');

console.log('\n================================================================');
console.log(`📊 ผลการทดสอบ: ผ่าน ${passedTests} จากทั้งหมด ${totalTests} ข้อ (${Math.round(passedTests/totalTests*100)}%)`);
console.log('================================================================\n');

if (passedTests === totalTests) {
  process.exit(0);
} else {
  process.exit(1);
}
