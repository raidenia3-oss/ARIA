# frozen_string_literal: true

module Aura
  class DSLCompiler
    def compile(rule_definition)
      {
        'rule' => rule_definition['name'],
        'event' => rule_definition['event'],
        'condition' => rule_definition['condition'],
        'actions' => rule_definition.fetch('actions', [])
      }
    end
  end
end
