// Navbar doc links follow the version being read, but Docusaurus marks every doc link of the same sidebar active (all
// pages share one sidebar), so all four lit up together. Keep the highlight on the link whose page (or a page under it)
// is open.
export function onRouteDidUpdate({location}) {
  for (const a of document.querySelectorAll('.navbar__items:not(.navbar__items--right) a.navbar__link')) {
    const href = new URL(a.href, location.href).pathname;
    const on = location.pathname === href || location.pathname.startsWith(href.endsWith('/') ? href : href + '/');
    a.classList.toggle('navbar__link--active', on);
    if (on) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  }
}
