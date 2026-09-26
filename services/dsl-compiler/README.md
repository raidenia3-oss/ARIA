# DSL Compiler

A lightweight Ruby compiler for AURA automation rules.

## Example

```ruby
require_relative 'lib/dsl_compiler'

compiler = Aura::DSLCompiler.new
compiled = compiler.compile(%q(rule "hf_space_down" do
  on event: :hf_health_check
  if status == 504 && retries > 3
    notify :discord, channel: :ops
    redeploy :hf_space
  end
end))
```
