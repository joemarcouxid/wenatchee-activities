# Something to do — Phone App Deployment

This folder is a Progressive Web App (PWA). It can be installed on iPhone,
iPad, Android, Windows, and macOS after the folder is hosted on an HTTPS website.

## Fastest deployment with GitHub Pages

1. Create or sign in to a GitHub account.
2. Create a new repository named `wenatchee-teen-activities`.
3. Upload every item from this folder, including:
   - index.html
   - manifest.webmanifest
   - service-worker.js
   - .nojekyll
   - the icons folder
4. Open the repository's Settings.
5. Select Pages.
6. Under Build and deployment, choose:
   - Source: Deploy from a branch
   - Branch: main
   - Folder: /(root)
7. Save.
8. GitHub will provide a public HTTPS address after deployment.

## Install on iPhone or iPad

1. Open the deployed address in Safari.
2. Tap the Share button.
3. Tap Add to Home Screen.
4. Confirm the app name and tap Add.

## Install on Android

1. Open the deployed address in Chrome.
2. Tap Install when prompted.
3. If the prompt does not appear, open Chrome's menu and choose
   Install app or Add to Home screen.

## Updating the app

Replace the changed files in the same GitHub repository. Visitors receive the
new version after the service worker updates. When changing major app files,
increase the cache name in service-worker.js from v1 to v2, v3, and so forth.

## Important

The main generator works offline after it has been opened once. External source
links still require internet access. Confirm current trail closures, permits,
weather, smoke, snow, venue hours, and water conditions before leaving.

## App-store publication

This same web app can later be packaged with Capacitor for Apple App Store and
Google Play distribution. Store submission requires developer accounts, native
build tools, screenshots, listing information, review, and usually a privacy
policy.
