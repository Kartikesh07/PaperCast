export default function Footer() {
  return (
    <footer className="w-full py-8 px-8 mt-auto">
      <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-white/25">
        <p>
          Built with Groq · Edge TTS · PyMuPDF · React
        </p>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/Kartikesh07/PaperCast"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white/50 transition-colors"
          >
            Source Code
          </a>
          <span>·</span>
          <span>PaperCast © {new Date().getFullYear()}</span>
        </div>
      </div>
    </footer>
  );
}
