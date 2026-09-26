# frozen_string_literal: true

require_relative '../lib/dsl_compiler'

RSpec.describe Aura::DSLCompiler do
  it 'compiles a rule into a JSON-friendly hash' do
    compiler = described_class.new
    source = <<~DSL
      rule "hf_space_down" do
        on event: :hf_health_check
        if status == 504 && retries > 3
          notify :discord, channel: :ops
          redeploy :hf_space
        end
      end
    DSL

    compiled = compiler.compile(source)

    expect(compiled['rule']).to eq('hf_space_down')
    expect(compiled['event']).to eq('hf_health_check')
    expect(compiled['condition']).to eq('status == 504 && retries > 3')
    expect(compiled['actions'].size).to eq(2)
  end

  it 'evaluates simple conditions from a context hash' do
    compiler = described_class.new
    compiled = {
      'condition' => 'status == 504 && retries > 3'
    }

    expect(compiler.evaluate(compiled, { 'status' => 504, 'retries' => 4 })).to be(true)
    expect(compiler.evaluate(compiled, { 'status' => 200, 'retries' => 4 })).to be(false)
  end

  it 'evaluates negated conditions' do
    compiler = described_class.new
    compiled = {
      'condition' => 'status != 504'
    }

    expect(compiler.evaluate(compiled, { 'status' => 200 })).to be(true)
    expect(compiler.evaluate(compiled, { 'status' => 504 })).to be(false)
  end

  it 'evaluates OR conditions' do
    compiler = described_class.new
    compiled = {
      'condition' => 'status == 504 || status == 502'
    }

    expect(compiler.evaluate(compiled, { 'status' => 504 })).to be(true)
    expect(compiler.evaluate(compiled, { 'status' => 502 })).to be(true)
    expect(compiler.evaluate(compiled, { 'status' => 200 })).to be(false)
  end
end
