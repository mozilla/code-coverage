module.exports = {
    "globals": {
        "waitIdle": true,
        "wait": true,
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
        "no-console": [
            "error",
            {
                "allow": ["error"]
            }
        ]    
    }
};
