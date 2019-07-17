const path = require('path');
const webpack = require('webpack');

module.exports = {
  mode: 'development',
  entry: {
    'dxr': './src/dxr.js',
    'searchfox': './src/searchfox.js',
    'socorro': './src/socorro.js',
    'hgmo': './src/hgmo.js',
  },
  plugins: [
    // Since some NodeJS modules expect to be running in Node, it is helpful
    // to set this environment var to avoid reference errors.
    new webpack.DefinePlugin({
      'process.env.NODE_ENV': JSON.stringify('production'),
    }),
  ],
  output: {
    path: path.resolve(__dirname, 'build'),
    filename: '[name].js'
  },
  resolve : {
    modules : ['src', 'assets'],
  },

  // This will expose source map files so that errors will point to your
  // original source files instead of the transpiled files.
  devtool: 'sourcemap',
};
