---
name: ansible-jinja2
description: "Use when WRITING or DEBUGGING Jinja2 expressions ({{ }}, filters, tests, ternary, loops), FIXING type-safety issues in ansible-core 2.20 (explicit int|bool|list conversion, None→'' for str type), or CONVERTING Python patterns to Jinja2 (list comprehensions→map/select, dict comprehensions→dict2items). Covers what IS and IS NOT supported in Jinja2 >= 3.1.0. Trigger: filter-chain, list-comprehension, ternary, dict2items, type-safety, None-to-empty"
---

# Jinja2 in Ansible (ansible-core 2.20)

## Version

ansible-core 2.20 requires **Jinja2 >= 3.1.0**. The minimum was set at 3.1.0 for native macro type support. Tested up to Jinja2 3.1.x.

---

## Syntax Contexts

| Context | Syntax | Purpose |
|---------|--------|---------|
| Inline expression | `{{ expr }}` | Evaluate and output a value |
| Control block | `{% for/if/set ... %}` | Loops, conditionals, assignments |
| Comment | `{# ... #}` | Ignored at render time |

**Ansible `when:` clauses are bare Jinja2 expressions — do NOT wrap them in `{{ }}`.**

```yaml
when: variable == 'value'        # correct
when: "{{ variable == 'value' }}" # wrong — double evaluation
```

---

## What IS NOT Supported Inside `{{ }}`

These are the most common mistakes. None of these Python constructs work inside `{{ }}`:

```yaml
# INVALID — list comprehension
value: "{{ [x for x in my_list] }}"

# INVALID — dict comprehension
value: "{{ {k: v for k, v in items} }}"

# INVALID — generator expression
value: "{{ (x for x in my_list) }}"

# INVALID — lambda
value: "{{ lambda x: x + 1 }}"

# INVALID — variable assignment with =
value: "{{ config['key'] = 'value' }}"
```

Use filters (`map`, `select`, `selectattr`, etc.) or the loop + `set_fact` accumulator pattern instead.

---

## Transforming Lists Without Comprehensions

### Extract an attribute from a list of dicts

```yaml
# Python: [item['name'] for item in users]
value: "{{ users | map(attribute='name') | list }}"
```

### Filter items by value

```yaml
# Python: [x for x in items if x == 'foo']
value: "{{ items | select('equalto', 'foo') | list }}"

# Python: [x for x in items if x != 'foo']
value: "{{ items | reject('equalto', 'foo') | list }}"
```

### Filter dicts by attribute value

```yaml
# Python: [u for u in users if u['active'] == true]
value: "{{ users | selectattr('active', 'equalto', true) | list }}"

# Python: [u for u in users if u['active'] != false]
value: "{{ users | rejectattr('active', 'equalto', false) | list }}"
```

### Filter dicts where attribute is defined / truthy

```yaml
value: "{{ users | selectattr('email', 'defined') | list }}"
value: "{{ items | selectattr('enabled') | list }}"  # truthy check
```

### Transform each item (map with a filter)

```yaml
# Apply a filter to every element:
value: "{{ items | map('upper') | list }}"
value: "{{ paths | map('basename') | list }}"
value: "{{ items | map('regex_replace', '^foo', 'bar') | list }}"
```

### Chain map + select

```yaml
# Extract names of active users only:
value: "{{ users | selectattr('active') | map(attribute='name') | list }}"
```

---

## Building Transformed Lists: Loop + set_fact Accumulator

When filters alone are insufficient (e.g., you need to build objects with multiple computed fields), use the two-task accumulator pattern:

```yaml
- name: Init result list
  ansible.builtin.set_fact:
    my_result: []

- name: Build result list
  ansible.builtin.set_fact:
    my_result: "{{ my_result + [{'schema': dep_schema, 'act': dep_act}] }}"
  vars:
    dep_schema: >-
      {{
        item.schema if (item is mapping and item.schema is defined)
        else item if (item is string)
        else none
      }}
    dep_act: >-
      {{
        (item.dep_action if (item is mapping and item.dep_action is defined)
        else 'on') | string | lower
      }}
  loop: "{{ source_list }}"
  when: dep_schema is not none and (dep_schema | string | length) > 0
```

**Key points:**
- `vars:` in a task defines per-iteration variables available in both the `set_fact` value and the `when` condition.
- Each derived expression is written exactly once — no duplication.
- The `when` filter replaces the comprehension's `if` clause.

---

## Ternary / Inline Conditionals

```yaml
# Simple ternary
value: "{{ 'yes' if condition else 'no' }}"

# Nested ternary
value: >-
  {{
    'install' if (installed_version | length == 0)
    else 'upgrade' if (version_relation == 'lt')
    else 'downgrade' if (version_relation == 'gt')
    else 'noop'
  }}

# Ternary filter (equivalent to above for two values)
value: "{{ condition | ternary('yes', 'no') }}"

# Default filter — return fallback when undefined or empty
value: "{{ my_var | default('fallback') }}"
value: "{{ my_var | default('fallback', true) }}"  # true = also fallback on empty string/0/false
```

---

## Tests (`is` keyword)

### Jinja2 built-in tests

```yaml
when: my_var is defined
when: my_var is not defined
when: my_var is none
when: my_var is not none
when: my_var is string
when: my_var is mapping          # dict
when: my_var is sequence         # list, tuple, string
when: my_var is iterable
when: my_var is number
when: my_var is integer
when: my_var is boolean
```

### Ansible-specific tests

```yaml
when: my_version is version('2.0', '>=')
when: my_str is match('^prefix')       # full-string regex
when: my_str is search('substring')    # substring regex
when: my_list is subset(other_list)
when: my_list is superset(other_list)
when: result is changed
when: result is failed
when: result is succeeded
when: path is file
when: path is directory
when: path is exists
```

---

## Filters Reference

### String

```yaml
"{{ value | upper }}"
"{{ value | lower }}"
"{{ value | trim }}"
"{{ value | replace('old', 'new') }}"
"{{ value | regex_replace('^prefix_', '') }}"
"{{ value | regex_search('pattern') }}"
"{{ value | split(',') }}"                    # split string into list
"{{ value | string }}"                        # cast to string
"{{ value | int }}"
"{{ value | float }}"
"{{ value | bool }}"
"{{ value | b64encode }}"
"{{ value | b64decode }}"
```

### List

```yaml
"{{ list | length }}"
"{{ list | first }}"
"{{ list | last }}"
"{{ list | unique }}"
"{{ list | sort }}"
"{{ list | reverse | list }}"
"{{ list | join(', ') }}"
"{{ list | flatten }}"
"{{ list | flatten(levels=1) }}"
"{{ list | union(other_list) }}"
"{{ list | intersect(other_list) }}"
"{{ list | difference(other_list) }}"
"{{ list | zip(other_list) | list }}"
"{{ list | min }}"
"{{ list | max }}"
"{{ list | sum }}"
```

### Dict

```yaml
"{{ dict | dict2items }}"                          # → [{key: k, value: v}, ...]
"{{ items | items2dict }}"                         # → {k: v, ...}
"{{ dict | combine(other_dict) }}"                 # merge, other_dict wins
"{{ dict | combine(other_dict, recursive=true) }}" # deep merge
"{{ dict.keys() | list }}"
"{{ dict.values() | list }}"
"{{ dict.items() | list }}"
```

### Type / Serialization

```yaml
"{{ value | to_json }}"
"{{ value | to_yaml }}"
"{{ value | to_nice_json }}"
"{{ value | to_nice_yaml }}"
"{{ string | from_json }}"
"{{ string | from_yaml }}"
"{{ value | type_debug }}"    # returns Python type name as string
```

### Path (executes on control node)

```yaml
"{{ path | basename }}"
"{{ path | dirname }}"
"{{ path | expanduser }}"
"{{ path | realpath }}"
```

---

## Variable Assignment in Templates

Assignment is only possible via block syntax, not inside `{{ }}`:

```yaml
# In a template file (.j2):
{% set ns = namespace(total=0) %}
{% for item in items %}
{% set ns.total = ns.total + item.value %}
{% endfor %}
Total: {{ ns.total }}
```

Inside Ansible task files you cannot use `{% set %}` — use `set_fact` instead.

---

## `jinja2_native` Mode

When `jinja2_native: true` (ansible.cfg or play vars), templates render to native Python types:

```yaml
# jinja2_native = false (default): always returns string
"{{ [1, 2, 3] }}"  →  "[1, 2, 3]"  (string)

# jinja2_native = true: returns Python list
"{{ [1, 2, 3] }}"  →  [1, 2, 3]   (list)
```

Does NOT apply to `ansible.builtin.template` module (file generation); only to variable expressions and the `template` lookup.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `[x for x in list]` in `{{ }}` | Use `map` / `select` / accumulator loop |
| `when: "{{ expr }}"` | Remove `{{ }}` — `when` auto-evaluates |
| `none \| string \| length > 0` passes because `none\|string` = `'None'` (len 4) | Use `is not none and (val \| string \| length) > 0` |
| `\| default('x')` doesn't catch empty string | Use `\| default('x', true)` |
| `is not undefined` (non-standard) | Use `is defined` |
| `is true` only matches boolean `True`, not truthy | Use `\| bool` for truthy coercion |
| Nested ternary without parentheses | Use `>-` block scalar and indent each branch |
| `length >= 0` as a guard for "non-empty" | Always true — use `length > 0` |
