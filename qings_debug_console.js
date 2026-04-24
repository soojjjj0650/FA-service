// ============================================================
//  Qings F12 Console 진단 스크립트
//  사용법: F12 → Console 탭 → 아래 코드 전체 복사 후 Enter
// ============================================================

// 1. Nexacro 전역 객체 확인
console.log("=== Nexacro 환경 확인 ===");
console.log("mainframe 있음?", typeof mainframe !== 'undefined');
console.log("nexacro 있음?", typeof nexacro !== 'undefined');

// 2. Apply 버튼 컴포넌트 직접 접근
console.log("\n=== Apply 버튼 접근 시도 ===");
try {
  var btn = mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply;
  console.log("버튼 객체:", btn);
  console.log("버튼 id:", btn ? btn.id : "없음");
  console.log("버튼 type:", btn ? typeof btn : "없음");
} catch(e) {
  console.log("에러:", e.message);
}

// 3. div_left 하위 컴포넌트 목록
console.log("\n=== div_left 컴포넌트 목록 ===");
try {
  var divLeft = mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left;
  console.log("div_left:", divLeft);
  if (divLeft && divLeft.form) {
    var keys = Object.keys(divLeft.form).filter(k => !k.startsWith('_'));
    console.log("하위 컴포넌트:", keys);
  }
} catch(e) {
  console.log("에러:", e.message);
}

// 4. Apply 버튼 클릭 시도
console.log("\n=== Apply 클릭 시도 ===");
try {
  var btn2 = mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply;
  if (btn2) {
    btn2.click();
    console.log("클릭 성공!");
  } else {
    console.log("버튼이 null 또는 undefined");
  }
} catch(e) {
  console.log("에러:", e.message);
}
