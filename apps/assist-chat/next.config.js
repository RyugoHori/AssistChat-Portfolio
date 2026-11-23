/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  // 画面左下の開発用のマーク（N）を出さない。エラーの表示はこれまでどおり出る
  devIndicators: false,
};

module.exports = nextConfig;
