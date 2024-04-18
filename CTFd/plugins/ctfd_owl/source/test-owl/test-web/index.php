<?php
echo '<pre style="font-size: 1.2rem;">';
echo '<b>[/flag]</b> ' . file_get_contents("/flag") . "<br>";
echo '<b>[$FLAG]</b> ' . getenv("FLAG") . "<br>";
echo '</pre>';