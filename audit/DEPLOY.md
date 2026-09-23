# Deploy (already done 2026-09-22; kept for redeploys)

    ssh cloud-ts 'mkdir -p /var/www/html/namedhosts/www.isyfert.com/enrich/citebench-audit && sudo -n install -d -o www-data -g graham -m 2775 /var/lib/syfert/citebench-audit'
    scp ~/projects/citebench/audit/index.html ~/projects/citebench/audit/save.php cloud-ts:/var/www/html/namedhosts/www.isyfert.com/enrich/citebench-audit/
    ssh cloud-ts 'cd /var/www/html/namedhosts/www.isyfert.com/enrich/citebench-audit && php -l index.html && php -l save.php'

The vhost parses .html as PHP; build_page.py escapes '<' in the embedded JSON so no `<?` reaches the page.
Anonymous curl should return 302 to accounts.google.com (vhost-wide OIDC gate).
