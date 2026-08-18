/**
 * 构建前端并上传 Vite 产物（JS/CSS）到七牛。
 * HTML 仍由 FastAPI 托管 frontend/dist；index.html 里的资源指向 CDN。
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { build } from 'vite';

import {
  loadBackendEnv,
  collectCodeAssetTargets,
  uploadTargetsInParallel,
  createQiniuUploadToken,
  getRequiredEnv,
  getZone,
  dryRun,
  projectRoot,
  publishStagingToLiveDist,
  partitionHtmlTargets,
  stagingDistDir,
  distDir,
  joinUrl,
  normalizePrefix,
  DEFAULT_CDN_BASE,
  DEFAULT_UPLOAD_CONCURRENCY,
} from './qiniu-deploy-shared.mjs';

import qiniu from 'qiniu';

async function main() {
  await loadBackendEnv();

  const rawCdn = (process.env.QINIU_CDN_DOMAIN || DEFAULT_CDN_BASE).trim();
  const cdnBase = rawCdn.startsWith('http://') || rawCdn.startsWith('https://')
    ? rawCdn
    : `https://${rawCdn.replace(/\/+$/, '')}`;
  const prefix = normalizePrefix(
    process.env.QINIU_FRONTEND_PREFIX || process.env.QINIU_DEPLOY_PREFIX,
  );
  const assetBase = joinUrl(cdnBase, prefix);

  console.log(`[deploy] building with asset base: ${assetBase}`);
  console.log('[deploy] 构建写入 dist-next/，JS 传完后再切到正在托管的 dist/');
  await fs.rm(stagingDistDir, { recursive: true, force: true });
  await build({
    root: projectRoot,
    base: assetBase,
    logLevel: 'info',
    build: {
      outDir: 'dist-next',
      reportCompressedSize: false,
      sourcemap: false,
      emptyOutDir: true,
      watch: null,
    },
  });

  const stagingAssetsDir = path.join(stagingDistDir, 'assets');
  const uploadTargets = await collectCodeAssetTargets(prefix, { assetsDir: stagingAssetsDir });
  if (uploadTargets.length === 0) {
    throw new Error(`No build assets found in ${stagingAssetsDir}`);
  }
  const { assetTargets, htmlTargets } = partitionHtmlTargets(uploadTargets);
  console.log(`[deploy] found ${uploadTargets.length} files under dist/assets`);

  if (dryRun) {
    console.log('[deploy] dry-run mode enabled, skipping Qiniu upload');
    for (const target of [...assetTargets, ...htmlTargets]) {
      console.log(`[deploy] would upload: ${target.remoteKey}`);
    }
    return;
  }

  const accessKey = getRequiredEnv('QINIU_ACCESS_KEY');
  const secretKey = getRequiredEnv('QINIU_SECRET_KEY');
  const bucket = getRequiredEnv('QINIU_BUCKET');
  const region = process.env.QINIU_REGION || process.env.QINIU_ZONE || 'z0';

  const mac = new qiniu.auth.digest.Mac(accessKey, secretKey);
  const uploadToken = createQiniuUploadToken(mac, bucket);
  const config = new qiniu.conf.Config();
  config.zone = getZone(region);
  config.useHttpsDomain = true;
  config.useCdnDomain = true;

  const uploadOptions = { uploadToken, config, mac, bucket };
  if (assetTargets.length) {
    console.log(`[deploy] uploading js/css first, concurrency: ${DEFAULT_UPLOAD_CONCURRENCY}`);
    await uploadTargetsInParallel(assetTargets, uploadOptions, { label: 'deploy' });
  }
  console.log('[deploy] js/css uploaded; publishing HTML to live dist/ last');
  const published = await publishStagingToLiveDist(stagingDistDir, distDir);
  console.log(`[deploy] live dist updated: ${published.otherFiles} assets, ${published.htmlFiles} html`);
  if (htmlTargets.length) {
    await uploadTargetsInParallel(htmlTargets, uploadOptions, { label: 'deploy' });
  }
  await fs.rm(stagingDistDir, { recursive: true, force: true });

  console.log('[deploy] upload completed successfully');
  console.log(`[deploy] dist/*.html now references CDN: ${assetBase}assets/...`);
  console.log('[deploy] 请在服务器执行（git pull 后 npm run deploy）；本机开发用 npm run build / npm run dev');
}

main().catch((error) => {
  console.error('[deploy] failed:', error.message);
  process.exitCode = 1;
});
