/**
 * Redirects to Vercel Blob seed cache files.
 *
 * Files served at: quantcontext.ai/api/data/{filename}
 * Redirects to:    SEED_DATA_BASE_URL/{filename}
 *
 * Set SEED_DATA_BASE_URL in Vercel environment variables after first upload.
 * The workflow prints the value at the end of each run.
 *
 * Supported files:
 *   sp500_tickers.json, nasdaq100_tickers.json, ff_factors.parquet, prices.parquet
 */

const ALLOWED_FILES = new Set([
  "sp500_tickers.json",
  "nasdaq100_tickers.json",
  "ff_factors.parquet",
  "prices.parquet",
]);

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ file: string }> }
) {
  const { file } = await params;

  if (!ALLOWED_FILES.has(file)) {
    return new Response("Not found", { status: 404 });
  }

  const base = process.env.SEED_DATA_BASE_URL;
  if (!base) {
    return new Response("Seed data not configured", { status: 503 });
  }

  return Response.redirect(`${base}/${file}`, 302);
}
