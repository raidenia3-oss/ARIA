// Standalone ESLint config for local linting.
//
// The project's primary `eslint.config.mjs` depends on
// `eslint-config-next`, whose parser (`next/dist/compiled/babel/eslint-parser`)
// is absent because the locally installed `next` is v9.3.3. This config uses
// the already-present `@typescript-eslint` parser instead, so we can lint the
// real source without a framework reinstall.

import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [".next/**", "node_modules/**", "out/**", "build/**"],
  },
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parserOptions: {
        project: false,
        ecmaFeatures: { jsx: true },
      },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    // Standalone CommonJS Node scripts (integration bots). require() is
    // legitimate here and they must not be converted to ESM (no "type":"module").
    files: ["**/*.js"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
);
