# PWA Icons

This directory should contain app icons for the Progressive Web App.

## Required Icons

Generate these from `/public/logo.png`:

- icon-72x72.png
- icon-96x96.png
- icon-128x128.png
- icon-144x144.png
- icon-152x152.png
- icon-192x192.png
- icon-384x384.png
- icon-512x512.png

## Generate Icons

Using ImageMagick:

```bash
cd frontend/public

# Generate all icon sizes
for size in 72 96 128 144 152 192 384 512; do
  convert logo.png -resize ${size}x${size} icons/icon-${size}x${size}.png
done
```

Or use an online tool like:
- https://realfavicongenerator.net
- https://favicon.io
- https://maskable.app (for maskable icons)

## Notes

- The 512x512 icon should be "maskable" (safe zone in center for rounded corners)
- The 192x192 icon is used for Android home screen
- The 152x152 icon is used for iOS
