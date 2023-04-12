const path = require('path');
const webpack = require('webpack');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin')
const MiniCssExtractPlugin = require('mini-css-extract-plugin');


module.exports = {
  entry: ['babel-polyfill', 'index.js'],
  output: {
    path: __dirname + '/dist',
    publicPath: '',
    filename: 'coverage-[hash].js'
  },
  plugins: [
    new CleanWebpackPlugin(),
    new HtmlWebpackPlugin({
      template: 'src/base.html',
    }),
    new MiniCssExtractPlugin({
      filename: 'coverage-[hash].css',
    }),
    new webpack.EnvironmentPlugin({
      BACKEND_URL: 'http://localhost:8000',
      REPOSITORY: 'https://hg.mozilla.org/mozilla-central',
      PROJECT: 'mozilla-central',
      ZERO_COVERAGE_REPORT: 'https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.production.cron.latest/artifacts/public/zero_coverage_report.json',
      USE_ISO_DATE: false,
    }),
  ],
  module: {
    rules: [
      {
        enforce: 'pre',
        test: /\.js$/,
        exclude: /node_modules/,
        loader: 'eslint-loader',
      },
      {
        test: /\.js$/,
        exclude: /(node_modules)/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env']
          }
        }
      },
      {
        test: /\.s[ac]ss$/i,
        use: [
          MiniCssExtractPlugin.loader,
          'css-loader',
          'sass-loader',
        ],
      },
      {
        test: /\.css$/i,
        use: [MiniCssExtractPlugin.loader, 'css-loader'],
      },
      {
        test: /\.(png|svg|jpg|gif)$/,
        use: [
          'file-loader'
        ]
      },
    ],
  },
	devServer: {
    contentBase: path.join(__dirname, 'dist'),
    compress: true,
    port: 9000
  },
  resolve: {
    modules: [
      path.join(__dirname, 'node_modules'),
      path.join(__dirname, 'assets'),
      path.join(__dirname, 'src'),
    ],
  },
}
