export default function Hero() {
  return (
    <section className="text-center max-w-3xl mx-auto pt-8 pb-12 px-4 animate-fade-in-up">
      <div className="inline-flex items-center gap-2 glass-sm px-4 py-1.5 mb-6 text-xs font-medium text-indigo-300 tracking-wide uppercase">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse-dot" />
        AI-Powered Research Podcasts
      </div>

      <h2 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight tracking-tight">
        <span className="bg-gradient-to-r from-white via-indigo-100 to-indigo-300 bg-clip-text text-transparent">
          Transform Papers
        </span>
        <br />
        <span className="bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
          Into Podcasts
        </span>
      </h2>

      <p className="mt-5 text-base sm:text-lg text-white/50 leading-relaxed max-w-xl mx-auto">
        Paste any arXiv link — get a two-host conversational podcast with
        natural dialogue, math explanations, and studio-quality audio.
      </p>
    </section>
  );
}
