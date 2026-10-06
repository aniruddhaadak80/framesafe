import { describe, expect, it } from 'vitest'
import { ValidationError } from './errors.js'
import { validateInput } from './validate.js'

const clipInput = {
  type: 'object',
  properties: {
    clip: { type: 'string', minLength: 1 },
    frame: { type: 'number', minimum: 0 },
    verbose: { type: 'boolean' },
  },
  required: ['clip'],
  additionalProperties: false,
} as const

describe('validateInput', () => {
  it('accepts a well-formed input', () => {
    expect(validateInput(clipInput, { clip: 'title-block' })).toEqual({ clip: 'title-block' })
  })

  it('rejects a missing required field and names it', () => {
    expect(() => validateInput(clipInput, {})).toThrow(/missing required field "clip"/)
  })

  it('rejects an undeclared field', () => {
    expect(() => validateInput(clipInput, { clip: 'x', sneaky: 1 })).toThrow(/undeclared field "sneaky"/)
  })

  it('rejects a wrong type and reports both types', () => {
    try {
      validateInput(clipInput, { clip: 7 })
      expect.unreachable()
    } catch (cause) {
      expect(cause).toBeInstanceOf(ValidationError)
      expect((cause as ValidationError).details).toMatchObject({ expected: 'string', received: 'number' })
    }
  })

  it('enforces numeric bounds', () => {
    expect(() => validateInput(clipInput, { clip: 'x', frame: -1 })).toThrow(/must be >= 0/)
  })

  it('rejects a non-object input', () => {
    expect(() => validateInput(clipInput, 'not-an-object')).toThrow(/input must be an object/)
  })

  it('refuses to run a schema that uses an unsupported keyword', () => {
    // A schema that silently ignores what it declares is worse than no schema at all.
    expect(() => validateInput({ type: 'object', patternProperties: {} }, {})).toThrow(
      /unsupported keyword "patternProperties"/,
    )
  })

  it('validates array items', () => {
    const schema = {
      type: 'object',
      properties: { ids: { type: 'array', items: { type: 'string' } } },
      required: ['ids'],
      additionalProperties: false,
    } as const
    expect(validateInput(schema, { ids: ['a', 'b'] })).toEqual({ ids: ['a', 'b'] })
    expect(() => validateInput(schema, { ids: ['a', 2] })).toThrow(/input.ids\[1\] must be string/)
  })
})
