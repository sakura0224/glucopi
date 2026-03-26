# WeChat Mini Program

This directory contains the cleaned WeChat Mini Program frontend migrated from the original workspace.

## Included

- `behaviors/`
- `components/`
- `config/`
- `custom-tab-bar/`
- `pages/`
- `static/`
- `utils/`
- `app.js`
- `app.json`
- `app.less`
- `config.js`
- `package.json`
- `package-lock.json`
- `project.config.json`
- `sitemap.json`
- `variable.less`

## Excluded

- `node_modules/`
- `miniprogram_npm/`
- `project.private.config.json`
- `.cloudbase/`
- `__MACOSX/`
- `.DS_Store`

## Notes

- Update `utils/api-config.js` with your real HTTP and WebSocket backend endpoints before running the app.
- Because `miniprogram_npm/` is intentionally excluded, dependencies may need to be installed and rebuilt in WeChat DevTools before local preview.
