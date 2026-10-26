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
})();
