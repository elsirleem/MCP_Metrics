/** @type {import('next').NextConfig} */
const nextConfig = {
	eslint: {
		// Skip ESLint during builds to keep production bundles moving; run lint locally when needed.
		ignoreDuringBuilds: true,
	},
};

module.exports = nextConfig;
