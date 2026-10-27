// Follow-up guides: figure images open at full size in a new tab (small terminal text is easier to read there).
document.querySelectorAll('figure img').forEach(function (img) {
  var a = document.createElement('a');
  a.href = img.getAttribute('src');
  a.target = '_blank';
  a.rel = 'noopener';
  a.className = 'zoom';
  a.title = '크게 보기';
  img.parentNode.insertBefore(a, img);
  a.appendChild(img);
});

// Copy buttons: every .box gets a "복사" button that copies its <pre> text.
document.querySelectorAll('.box').forEach(function (box) {
  var pre = box.querySelector('pre');
  if (!pre) return;
  var b = document.createElement('button');
  b.type = 'button';
  b.className = 'copy';
  b.textContent = '복사';
  b.addEventListener('click', function () {
    var text = pre.innerText;
    var done = function () {
      b.textContent = '복사됨';
      b.classList.add('done');
      setTimeout(function () { b.textContent = '복사'; b.classList.remove('done'); }, 1500);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, function () {});
    } else {
      var t = document.createElement('textarea');
      t.value = text; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); done(); } catch (e) {}
      document.body.removeChild(t);
    }
  });
  box.appendChild(b);
});
