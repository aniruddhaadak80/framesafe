/**
 * The public facade. It re-exports the stable surface and nothing else — if a consumer can
 * reach an internal module from here, a boundary has been broken.
 *
 * The omitted surfaces (desktop, channels, model providers) are absent here for the same
 * reason they are absent from the workspace: they were never built, and a facade that
 * re-exports a surface that does not exist is a lie about the product.
 */
export * from '@framesafe/core'
export * from '@framesafe/skills'
export * from '@framesafe/plugins'
export * from '@framesafe/memory'
export * from '@framesafe/engine-client'
