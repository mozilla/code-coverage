module.exports = {
    "globals": {
        "waitIdle": true,
        "wait": true,
        "fetch": true,
        "fetchCoverage": true,
        "fetchAnnotate": true,
        "fetchChangesetCoverage": true,
        "isCoverageSupported": true,
        "injectToggle": true,
        "getPath": true,
        "gitToHg": true,
        "getNavigationPanel": true,
        "SUPPORTED_EXTENSIONS": true
    },
    "env": {
        "es6": true,
        "node": true,
        "webextensions": true
    },
    "plugins": [
        "mozilla"
    ],
    "extends": [
        "plugin:mozilla/recommended",
        "eslint:recommended"
    ],
    "parserOptions": {
        "ecmaVersion": 8,
        "ecmaFeatures": {
            "jsx": true
        },
        "sourceType": "module"
    },
    "rules": {
        "indent": [
            "error",
            2
        ],
        "linebreak-style": [
            "error",
            "windows"
        ],
        "quotes": [
            "warn",
            "single"
        ],
        "no-unused-vars": [
            "warn",
            "all"
        ],
        "no-constant-condition": [
            "warn"
        ],
        "no-console": "off"
        
    }
};