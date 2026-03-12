let
  pkgs = import <nixpkgs> { };
in
pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (
      ps: with ps; [
        requests
        (ps.buildPythonPackage {
          pname = "pdf2bib";
          version = "1.2";
          pyproject = true;
          src = pkgs.fetchFromGitHub {
            owner = "bileamScheuvens";
            repo = "pdf2bib";
            rev = "master";
            hash = "sha256-1cAZlThoIN2L7/c0YDq+XwbbcLMWSt0VpRl7oHVq1hg=";
          };
          buildInputs = [ ps.setuptools ];
          propagatedBuildInputs = [
            unidecode
            bibtexparser
            (ps.buildPythonPackage {
              pname = "pdf2doi";
              version = "1.7";
              pyproject = true;
              src = pkgs.fetchFromGitHub {
                owner = "sherjeelshabih";
                repo = "pdf2doi";
                rev = "fix-missing-config-in-wheel";
                hash = "sha256-UzOvZrMzuPl4I27sqPsDK5/kTC+Vw0pyWRvLXrGckHg=";
              };
              buildInputs = [ ps.setuptools ];
              propagatedBuildInputs = [
                ps.google
                ps.requests
                (ps.buildPythonPackage {
                  pname = "pypdf2";
                  version = "2.12.1";
                  pyproject = true;
                  src = ps.fetchPypi {
                    pname = "PyPDF2";
                    version = "2.12.1";
                    sha256 = "sha256-4D7xirzHXadBoKzBp3SSU0loh744zZiHvM4c7jk9pF4=";
                  };
                  buildInputs = [
                    ps.setuptools
                    ps.flit-core
                  ];
                  propagatedBuildInputs = [
                  ];
                })
                ps.feedparser
                ps.pyperclip
                ps.easygui
                ps.pypdf
                ps.pymupdf
                (ps.buildPythonPackage {
                  pname = "pdftitle";
                  version = "0.20";
                  pyproject = true;
                  src = ps.fetchPypi {
                    pname = "pdftitle";
                    version = "0.20";
                    sha256 = "sha256-IhXf3s6Fzsl1+cb+vYVfl6ohV8+mtJDQvh8C9CiOgA4=";
                  };
                  buildInputs = [ ps.setuptools ];
                  propagatedBuildInputs = [
                    ps.pdfminer-six
                    ps.python-dotenv
                  ];
                })
              ];
              dontCheckRuntimeDeps = true;
              doCheck = false;
            })
          ];
          dontCheckRuntimeDeps = true;
          doCheck = false;
        })
      ]
    ))
  ];

}
