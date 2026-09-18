import sys
import pathlib
import logging
from os import fspath

global_ = logging.getLogger(__name__)

src_path = pathlib.Path(__file__).parent.parent

sys.path.append(fspath(src_path))

global_.info("use {} gloabl sys path add src path.".format(__file__))