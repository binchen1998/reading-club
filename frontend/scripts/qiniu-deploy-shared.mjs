import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import qiniu from 'qiniu';

export const DEFAULT_UPLOAD_CONCURRENCY = 8;
export const DEFAULT_CDN_BASE = 'https://static1.cxy61.com/';
export const DEFAULT_PREFIX = 'reading-club';
export const dryRun = process.argv.includes('--dry-run');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const projectRoot = path.resolve(__dirname, '..');
export const repoRoot = path.resolve(projectRoot, '..');
export const distDir = path.join(projectRoot, 'dist');
export const stagingDistDir = path.join(projectRoot, 'dist-next');
export const assetsDir = path.join(distDir, 'assets');

export function trimSlashes(value) {
  return value.replace(/^\/+|\/+$/g, '');
}

export function normalizePrefix(value) {
  const trimmed = trimSlashes(value || DEFAULT_PREFIX);
  return trimmed || DEFAULT_PREFIX;
}

export function joinUrl(base, ...parts) {
  const cleanedBase = base.replace(/\/+$/, '');
  const cleanedParts = parts.filter(Boolean).map((part) => trimSlashes(part)).filter(Boolean);
  return `${cleanedBase}/${cleanedParts.join('/')}/`;
}

function parseEnvLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) return null;
  const separatorIndex = trimmed.indexOf('=');
  if (separatorIndex <= 0) return null;
  const key = trimmed.slice(0, separatorIndex).trim();
  let value = trimmed.slice(separatorIndex + 1).trim();
  if (
    (value.startsWith('"') && value.endsWith('"'))
    || (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1);
  }
  return [key, value];
}

async function loadEnvFile(filePath) {
  let content = '';
  try {
    content = await fs.readFile(filePath, 'utf8');
  } catch (error) {
    if (error && error.code === 'ENOENT') return;
    throw error;
  }
  for (const line of content.split(/\r?\n/)) {
    const parsed = parseEnvLine(line);
    if (!parsed) continue;
    const [key, value] = parsed;
    if (!(key in process.env)) process.env[key] = value;
  }
}

export async function loadBackendEnv() {
  await loadEnvFile(path.join(repoRoot, 'backend', '.env'));
  await loadEnvFile(path.join(repoRoot, '.env'));
}

export function getRequiredEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

export function getZone(region) {
  const zoneMap = {
    z0: qiniu.zone.Zone_z0,
    z1: qiniu.zone.Zone_z1,
    z2: qiniu.zone.Zone_z2,
    na0: qiniu.zone.Zone_na0,
    as0: qiniu.zone.Zone_as0,
  };
  return zoneMap[(region || 'z0').toLowerCase()] || qiniu.zone.Zone_z0;
}

export function createQiniuUploadToken(mac, bucket) {
  const putPolicy = new qiniu.rs.PutPolicy({
    scope: bucket,
    insertOnly: 0,
  });
  return putPolicy.uploadToken(mac);
}

export async function walkFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(dir, entry.name);
    return entry.isDirectory() ? walkFiles(fullPath) : [fullPath];
  }));
  return files.flat().sort();
}

export async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

function formatQiniuBody(body) {
  if (body == null) return '';
  if (typeof body === 'string') return body.slice(0, 400);
  try {
    return JSON.stringify(body).slice(0, 400);
  } catch {
    return '';
  }
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function deleteRemoteObject({ mac, config, bucket, remoteKey }) {
  const bm = new qiniu.rs.BucketManager(mac, config);
  return new Promise((resolve, reject) => {
    bm.delete(bucket, remoteKey, (err, body, info) => {
      if (err) {
        reject(err);
        return;
      }
      if ((info.statusCode >= 200 && info.statusCode < 300) || info.statusCode === 612) {
        resolve();
        return;
      }
      reject(new Error(`Qiniu delete failed for ${remoteKey}: HTTP ${info.statusCode} ${formatQiniuBody(body)}`));
    });
  });
}

function putFileOnce({ uploadToken, config, localFile, remoteKey }) {
  const resumeUploader = new qiniu.resume_up.ResumeUploader(config);
  const putExtra = qiniu.resume_up.PutExtra.create();
  return new Promise((resolve, reject) => {
    resumeUploader.putFileV2(uploadToken, remoteKey, localFile, putExtra, (err, body, info) => {
      if (err) {
        reject(err);
        return;
      }
      if (info.statusCode >= 200 && info.statusCode < 300) {
        resolve(body);
        return;
      }
      const error = new Error(`Qiniu upload failed for ${remoteKey}: HTTP ${info.statusCode} ${formatQiniuBody(body)}`);
      error.statusCode = info.statusCode;
      reject(error);
    });
  });
}

export async function uploadFile({ uploadToken, config, localFile, remoteKey, mac, bucket }) {
  const { size } = await fs.stat(localFile);
  console.log(`[deploy] upload ${remoteKey} (${formatFileSize(size)})`);
  try {
    await putFileOnce({ uploadToken, config, localFile, remoteKey });
  } catch (firstError) {
    if (firstError?.statusCode === 614 && mac && bucket) {
      await deleteRemoteObject({ mac, config, bucket, remoteKey });
      await putFileOnce({ uploadToken, config, localFile, remoteKey });
      return;
    }
    throw firstError;
  }
}

export async function uploadTargetsInParallel(uploadTargets, uploadOptions, options) {
  const { maxConcurrency = DEFAULT_UPLOAD_CONCURRENCY } = options || {};
  let nextIndex = 0;
  const total = uploadTargets.length;
  async function worker() {
    while (true) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      if (currentIndex >= total) return;
      const target = uploadTargets[currentIndex];
      await uploadFile({
        ...uploadOptions,
        localFile: target.localFile,
        remoteKey: target.remoteKey,
      });
    }
  }
  await Promise.all(Array.from({ length: Math.min(maxConcurrency, total) }, () => worker()));
}

export function partitionHtmlTargets(uploadTargets) {
  const assetTargets = [];
  const htmlTargets = [];
  for (const target of uploadTargets) {
    if (typeof target?.remoteKey === 'string' && target.remoteKey.toLowerCase().endsWith('.html')) {
      htmlTargets.push(target);
    } else {
      assetTargets.push(target);
    }
  }
  return { assetTargets, htmlTargets };
}

export async function publishStagingToLiveDist(fromDir, toDir) {
  const files = await walkFiles(fromDir);
  const htmlFiles = [];
  const otherFiles = [];
  for (const file of files) {
    if (file.toLowerCase().endsWith('.html')) htmlFiles.push(file);
    else otherFiles.push(file);
  }
  htmlFiles.sort((a, b) => {
    const aIndex = path.basename(a) === 'index.html' ? 1 : 0;
    const bIndex = path.basename(b) === 'index.html' ? 1 : 0;
    return aIndex - bIndex;
  });
  for (const src of [...otherFiles, ...htmlFiles]) {
    const dest = path.join(toDir, path.relative(fromDir, src));
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(src, dest);
  }
  return { otherFiles: otherFiles.length, htmlFiles: htmlFiles.length };
}

export async function collectCodeAssetTargets(prefix, options = {}) {
  const fromAssetsDir = options.assetsDir || assetsDir;
  const targets = [];
  if (!(await pathExists(fromAssetsDir))) return targets;
  for (const localFile of await walkFiles(fromAssetsDir)) {
    const relativePath = path.relative(fromAssetsDir, localFile).split(path.sep).join('/');
    targets.push({
      localFile,
      remoteKey: `${prefix}/assets/${relativePath}`,
    });
  }
  return targets;
}
