import { ValidationError } from './errors.js'
import type { JsonSchema } from './types.js'

/**
 * Input validation at the narrow waist.
 *
 * Every tool's input is checked against its declared `inputSchema` before the handler
 * runs. That is what makes the MCP surface safe to expose to a model: a model cannot
 * smuggle an undeclared field past the boundary, and a handler never has to defend itself
 * against a wrong type.
 *
 * This is a deliberately small subset of JSON Schema — the keywords the tool contract
 * actually uses. An unrecognised keyword is a validation *error* rather than a silent
 * pass, because a schema that quietly does nothing is worse than no schema at all.
 */

const SUPPORTED_KEYWORDS = new Set([
  'type',
  'properties',
  'required',
  'additionalProperties',
  'items',
  'enum',
  'minimum',
  'maximum',
  'minLength',
  'maxLength',
  'pattern',
  'description',
  'default',
])

function assertSupported(schema: JsonSchema, path: string): void {
  for (const keyword of Object.keys(schema)) {
    if (!SUPPORTED_KEYWORDS.has(keyword)) {
      throw new ValidationError(`schema at ${path} uses unsupported keyword "${keyword}"`, {
        path,
        keyword,
        supported: [...SUPPORTED_KEYWORDS],
      })
    }
  }
  const properties = schema['properties']
  if (properties !== undefined && typeof properties === 'object' && properties !== null) {
    for (const [name, child] of Object.entries(properties)) {
      if (typeof child !== 'object' || child === null) {
        throw new ValidationError(`schema at ${path}.${name} must be an object`, { path })
      }
      assertSupported(child as JsonSchema, `${path}.${name}`)
    }
  }
  const items = schema['items']
  if (items !== undefined) {
    if (typeof items !== 'object' || items === null) {
      throw new ValidationError(`schema at ${path}.items must be an object`, { path })
    }
    assertSupported(items as JsonSchema, `${path}.items`)
  }
}

function typeOf(value: unknown): string {
  if (Array.isArray(value)) return 'array'
  if (value === null) return 'null'
  return typeof value
}

function checkScalar(schema: JsonSchema, value: unknown, path: string): void {
  const expected = schema['type']
  if (typeof expected === 'string' && typeOf(value) !== expected) {
    throw new ValidationError(`${path} must be ${expected}, got ${typeOf(value)}`, {
      path,
      expected,
      received: typeOf(value),
    })
  }

  const allowed = schema['enum']
  if (Array.isArray(allowed) && !allowed.includes(value)) {
    throw new ValidationError(`${path} must be one of ${JSON.stringify(allowed)}`, {
      path,
      allowed,
      received: value,
    })
  }

  if (typeof value === 'number') {
    const minimum = schema['minimum']
    const maximum = schema['maximum']
    if (typeof minimum === 'number' && value < minimum) {
      throw new ValidationError(`${path} must be >= ${minimum}, got ${value}`, { path, minimum })
    }
    if (typeof maximum === 'number' && value > maximum) {
      throw new ValidationError(`${path} must be <= ${maximum}, got ${value}`, { path, maximum })
    }
  }

  if (typeof value === 'string') {
    const minLength = schema['minLength']
    const maxLength = schema['maxLength']
    const pattern = schema['pattern']
    if (typeof minLength === 'number' && value.length < minLength) {
      throw new ValidationError(`${path} must be at least ${minLength} characters`, { path })
    }
    if (typeof maxLength === 'number' && value.length > maxLength) {
      throw new ValidationError(`${path} must be at most ${maxLength} characters`, { path })
    }
    if (typeof pattern === 'string' && !new RegExp(pattern).test(value)) {
      throw new ValidationError(`${path} must match ${pattern}, got "${value}"`, { path, pattern })
    }
  }
}

/**
 * Validate `input` against `schema`, returning the same value typed as a record.
 *
 * Undeclared properties are rejected when `additionalProperties: false`, which is how a
 * tool tells a model "this exact shape, no more".
 */
export function validateInput(schema: JsonSchema, input: unknown): Record<string, unknown> {
  assertSupported(schema, 'input')
  if (typeOf(input) !== 'object') {
    throw new ValidationError(`input must be an object, got ${typeOf(input)}`, {
      received: typeOf(input),
    })
  }

  const record = input as Record<string, unknown>
  const properties = (schema['properties'] ?? {}) as Record<string, JsonSchema>
  const required = (schema['required'] ?? []) as string[]

  for (const name of required) {
    if (!(name in record) || record[name] === undefined) {
      throw new ValidationError(`input is missing required field "${name}"`, { field: name })
    }
  }

  for (const [name, value] of Object.entries(record)) {
    const child = properties[name]
    if (child === undefined) {
      if (schema['additionalProperties'] === false) {
        throw new ValidationError(`input has undeclared field "${name}"`, {
          field: name,
          allowed: Object.keys(properties),
        })
      }
      continue
    }
    checkScalar(child, value, `input.${name}`)
    const childType = child['type']
    if (childType === 'object' && typeOf(value) === 'object') {
      validateInput(child, value)
    }
    if (childType === 'array' && Array.isArray(value)) {
      const items = child['items']
      if (items !== undefined) {
        value.forEach((entry, index) => {
          checkScalar(items as JsonSchema, entry, `input.${name}[${index}]`)
        })
      }
    }
  }

  return record
}
