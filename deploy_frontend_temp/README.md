# Public Assets

This folder contains static assets that are served directly by Vite without processing.

## Folder Structure

- **`images/`** - Application images, logos, photos, etc.
- **`icons/`** - Icon files (favicon.ico, app icons, etc.)
- **`assets/`** - Other static assets (documents, downloads, etc.)

## Usage

Files in this folder can be referenced in your code using absolute paths from the root:

```tsx
// Reference an image
<img src="/images/logo.png" alt="Logo" />

// Reference an icon
<link rel="icon" href="/icons/favicon.ico" />

// Reference other assets
<a href="/assets/document.pdf">Download PDF</a>
```

## Notes

- Files are served as-is without any build processing
- Use this for assets that don't need optimization or processing
- For assets that should be processed (optimized, bundled), import them directly in your components instead
