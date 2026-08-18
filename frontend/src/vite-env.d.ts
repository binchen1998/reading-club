/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ASSET_BASE?: string
  readonly VITE_SERIES_COVERS_JSON_URL?: string
}
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}
