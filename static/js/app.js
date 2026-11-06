(function () {
  var header = document.querySelector('.site-header');
  var navBtn = document.querySelector('[data-nav-toggle]');
  if (navBtn && header) {
    navBtn.addEventListener('click', function () {
      var open = header.classList.toggle('is-open');
      navBtn.setAttribute('aria-expanded', String(open));
    });
  }

  function closeDropdowns(except) {
    document.querySelectorAll('[data-dropdown]').forEach(function (dd) {
      if (dd === except) return;
      dd.querySelector('[data-dropdown-menu]').hidden = true;
      dd.querySelector('[data-dropdown-toggle]').setAttribute('aria-expanded', 'false');
    });
  }
  document.querySelectorAll('[data-dropdown]').forEach(function (dd) {
    var btn = dd.querySelector('[data-dropdown-toggle]');
    var menu = dd.querySelector('[data-dropdown-menu]');
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      closeDropdowns(dd);
      menu.hidden = !menu.hidden;
      btn.setAttribute('aria-expanded', String(!menu.hidden));
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('[data-dropdown]')) closeDropdowns();
    var close = e.target.closest('[data-dismiss]');
    if (close) close.closest('.alert').remove();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDropdowns(); });
  // Chống bấm đúp nút gửi form: lần gửi đầu thêm is-loading cho nút, các lần bấm sau bị chặn.
  document.addEventListener('submit', function (e) {
    if (e.defaultPrevented) return;   // trang tự xử lý gửi form bằng JavaScript (AJAX) thì để trang đó tự quản nút, không thêm is-loading
    var form = e.target;
    if (form.dataset.submitting === 'true') {   // đã gửi rồi -> chặn gửi lần nữa
      e.preventDefault();
      return;
    }
    form.dataset.submitting = 'true';
    var btn = e.submitter || form.querySelector('button[type="submit"]');
    if (btn) btn.classList.add('is-loading');
  });

  // Quay lại bằng nút Back của trình duyệt thì trả form về trạng thái bình thường.
  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    document.querySelectorAll('form[data-submitting]').forEach(function (f) {
      delete f.dataset.submitting;
      f.querySelectorAll('.is-loading').forEach(function (b) { b.classList.remove('is-loading'); });
    });
  });
})();
