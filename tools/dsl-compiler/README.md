# DSL Compiler

A Ruby-based rule compiler that turns concise Ruby-like rules into JSON for Python evaluation.

## Example

```ruby
rule "hf_space_down" do
  on event: :hf_health_check
  if status == 504 && retries > 3
    notify :discord, channel: :ops
    redeploy :hf_space
  end
end
```
