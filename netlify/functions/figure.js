// Netlify Function: serves figure images from the Netlify Blob store `figures`.
// Request path: /figures/<key>  (e.g. /figures/paper_aa_hl_p1/abc.jpg)
// The blob key is the same relative path used locally under backend/public/figures.
import { getStore } from '@netlify/blobs';

const MIME = {
  jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif',
  webp: 'image/webp', svg: 'image/svg+xml', avif: 'image/avif'
};

export const handler = async (event) => {
  // Netlify may deliver the path as /figure/<splat> or /figures/<splat>; strip either.
  const key = (event.path || '').replace(/^\/(figure|figures)\//, '');
  if (!key) return { statusCode: 400, body: 'missing key' };

  let data;
  try {
    // CLI deploys don't auto-inject the Blobs runtime env, so pass credentials
    // explicitly. NETLIFY_SITE_ID + NETLIFY_AUTH_TOKEN are set on the site.
    const store = getStore({
      name: 'figures',
      siteID: process.env.NETLIFY_SITE_ID,
      token: process.env.NETLIFY_AUTH_TOKEN
    });
    data = await store.get(key, { type: 'arrayBuffer' });
  } catch (e) {
    return { statusCode: 500, body: `blob error: ${e.message}` };
  }
  if (!data) return { statusCode: 404, body: 'not found' };

  const ext = key.split('.').pop().toLowerCase();
  const contentType = MIME[ext] || 'application/octet-stream';
  return {
    statusCode: 200,
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'public, max-age=31536000, immutable',
      'Access-Control-Allow-Origin': '*'
    },
    body: Buffer.from(data).toString('base64'),
    isBase64Encoded: true
  };
};
