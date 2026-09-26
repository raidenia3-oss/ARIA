require_relative '../lib/dsl_compiler'

RSpec.describe Aura::DSLCompiler do
  it 'compiles a rule definition into JSON-friendly output' do
    compiler = described_class.new
    result = compiler.compile({
      'name' => 'hf_space_down',
      'event' => 'hf_health_check',
      'condition' => 'status == 504 && retries > 3',
      'actions' => ['notify:discord', 'redeploy:hf_space']
    })

    expect(result['rule']).to eq('hf_space_down')
    expect(result['actions']).to include('redeploy:hf_space')
  end
end
