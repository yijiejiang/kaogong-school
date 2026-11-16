import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "考公私塾",
    short_name: "考公私塾",
    description: "个人考公多智能体辅导系统：资料、出卷、改卷、学情与计划。",
    start_url: "/",
    display: "standalone",
    background_color: "#f7f4ee",
    theme_color: "#b5462f",
    orientation: "portrait",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/apple-touch-icon.png",
        sizes: "180x180",
        type: "image/png",
        purpose: "any",
      },
    ],
  };
}
