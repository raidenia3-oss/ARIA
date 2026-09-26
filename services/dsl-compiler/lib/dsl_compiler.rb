# frozen_string_literal: true

module Aura
  class DSLCompiler
    def compile(source)
      return source if source.is_a?(Hash)

      rule_name = extract_rule_name(source)
      event_name = extract_event(source)
      condition = extract_condition(source)
      actions = extract_actions(source)

      {
        'rule' => rule_name,
        'event' => event_name,
        'condition' => condition,
        'actions' => actions
      }
    end

    def evaluate(compiled_rule, context = {})
      condition = compiled_rule['condition'] || compiled_rule[:condition]
      return false if condition.nil? || condition.strip.empty?

      or_segments = condition.split(/\s+\|\|\s+/)
      or_segments.any? do |or_segment|
        and_segments = or_segment.split(/\s+&&\s+/)
        and_segments.all? { |segment| evaluate_comparison(segment.strip, context) }
      end
    end

    private

    def extract_rule_name(source)
      match = source.match(/rule\s+"([^"]+)"/i)
      match ? match[1] : 'unnamed_rule'
    end

    def extract_event(source)
      match = source.match(/on\s+event:\s+:([a-z_]+)/i)
      match ? match[1] : nil
    end

    def extract_condition(source)
      match = source.match(/if\s+(.+?)(?:\n|$)/im)
      match ? match[1].strip : nil
    end

    def extract_actions(source)
      source.scan(/(notify|redeploy)\s+:([a-z_]+)/i).map do |action, target|
        { 'type' => action.downcase, 'target' => target.downcase }
      end
    end

    def evaluate_comparison(segment, context)
      negated = segment.start_with?('!')
      segment = segment[1..] if negated

      match = segment.match(/([a-z_]+)\s*(==|!=|>=|<=|>|<)\s*(.+)/i)
      return false unless match

      variable = match[1]
      operator = match[2]
      value = parse_literal(match[3])
      lhs = context[variable] || context[variable.to_sym]
      result = compare_values(lhs, operator, value)
      negated ? !result : result
    end

    def parse_literal(token)
      token = token.to_s.strip
      return token.delete('"').delete("'") unless token.match?(/^-?\d+$/)

      token.to_i
    end

    def compare_values(left, operator, right)
      case operator
      when '=='
        left == right
      when '!='
        left != right
      when '>'
        left > right
      when '>='
        left >= right
      when '<'
        left < right
      when '<='
        left <= right
      else
        false
      end
    end
  end
end
