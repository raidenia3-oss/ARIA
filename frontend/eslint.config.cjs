const react = require("eslint-plugin-react");
const reactHooks = require("eslint-plugin-react-hooks");
const jsxA11y = require("eslint-plugin-jsx-a11y");
const tsEslint = require("@typescript-eslint/eslint-plugin");
const next = require("@next/eslint-plugin-next");
const importPlugin = require("eslint-plugin-import");

module.exports = [
  {
    ignores: [".next", ".next/**", "**/.next/**", "out", "out/**", "build", "build/**", "next-env.d.ts"],
    languageOptions: {
      parser: require.resolve("@typescript-eslint/parser"),
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: "detect" },
      "import/parsers": {
        [require.resolve("@typescript-eslint/parser")]: [
          ".ts",
          ".tsx",
          ".mts",
          ".cts",
          ".js",
          ".jsx",
        ],
      },
      "import/resolver": {
        node: { extensions: [".js", ".jsx", ".ts", ".tsx"] },
        typescript: { alwaysTryTypes: true },
      },
    },
  },
  react.configs.flat.recommended,
  react.configs.flat["jsx-runtime"],
  reactHooks.configs["recommended-latest"],
  jsxA11y.flatConfigs.recommended,
  ...tsEslint.configs["flat/recommended"],
  next.flatConfig.recommended,
  next.flatConfig.coreWebVitals,
  {
    files: ["**/*.js"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
];
