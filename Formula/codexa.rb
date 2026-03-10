class Codexa < Formula
  include Language::Python::Virtualenv

  desc "Developer intelligence CLI — semantic code search, AI-assisted understanding, and workspace tooling"
  homepage "https://github.com/M9nx/CodexA"
  url "https://github.com/M9nx/CodexA/archive/refs/tags/v0.30.0.tar.gz"
  license "MIT"

  depends_on "python@3.12"
  depends_on "ripgrep" => :recommended

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"codexa", "--version"
  end
end
