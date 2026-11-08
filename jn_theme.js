// Shared by jn_web.html (/) and jn_pm.html (/pm), served at /theme.js. The choice lives in localStorage
// (jn.theme, jn.mode), so both pages follow it.
// ---- themes: base16 palettes (base00 bg ... base05 fg ... base08-0F accents); acc names the slot used as the accent.
// Sources: vague2k/vague.nvim lua/vague/config/internal.lua; sainnhe/everforest autoload/everforest.vim (medium);
// projekt0n/github-nvim-theme palette/github_dark_default.lua + github_light_default.lua (primitives). Add one = add an entry.
const THEMES = {
  vague: { acc: 'base0D',
    dark: { base00:'#141415', base01:'#1c1c24', base02:'#333738', base03:'#606079', base04:'#878787', base05:'#cdcdcd', base06:'#c3c3d5', base07:'#c3c3d5', base08:'#d8647e', base09:'#e0a363', base0A:'#f3be7c', base0B:'#7fa563', base0C:'#b4d4cf', base0D:'#6e94b2', base0E:'#bb9dbd', base0F:'#c48282' } },
  everforest: { acc: 'base0B',
    dark: { base00:'#2d353b', base01:'#343f44', base02:'#475258', base03:'#859289', base04:'#9da9a0', base05:'#d3c6aa', base06:'#d3c6aa', base07:'#d3c6aa', base08:'#e67e80', base09:'#e69875', base0A:'#dbbc7f', base0B:'#a7c080', base0C:'#83c092', base0D:'#7fbbb3', base0E:'#d699b6', base0F:'#7a8478' },
    light: { base00:'#fdf6e3', base01:'#f4f0d9', base02:'#e6e2cc', base03:'#939f91', base04:'#829181', base05:'#5c6a72', base06:'#5c6a72', base07:'#5c6a72', base08:'#f85552', base09:'#f57d26', base0A:'#dfa000', base0B:'#8da101', base0C:'#35a77c', base0D:'#3a94c5', base0E:'#df69ba', base0F:'#a6b0a0' } },
  github: { acc: 'base0D',
    dark: { base00:'#0d1117', base01:'#161b22', base02:'#30363d', base03:'#6e7681', base04:'#8b949e', base05:'#e6edf3', base06:'#f0f6fc', base07:'#f0f6fc', base08:'#ff7b72', base09:'#f0883e', base0A:'#d29922', base0B:'#3fb950', base0C:'#76e3ea', base0D:'#58a6ff', base0E:'#bc8cff', base0F:'#f778ba' },
    light: { base00:'#ffffff', base01:'#f6f8fa', base02:'#d0d7de', base03:'#57606a', base04:'#32383f', base05:'#1f2328', base06:'#24292f', base07:'#1f2328', base08:'#cf222e', base09:'#bc4c00', base0A:'#9a6700', base0B:'#116329', base0C:'#1b7c83', base0D:'#0969da', base0E:'#8250df', base0F:'#953800' } },
};

function jnPalette() {  // {p: the 16 colors, acc: the accent slot} for the saved scheme and mode; a scheme without that variant uses the one it has
  let name = 'github', mode = 'system';
  try { name = localStorage.getItem('jn.theme') || name; mode = localStorage.getItem('jn.mode') || mode; } catch {}
  const t = THEMES[name] || THEMES.github, want = mode === 'system' ? (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark') : mode;
  return { p: t[want] || t.dark || t.light, acc: t.acc };
}
