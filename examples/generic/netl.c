/*
 * Generic netlink sample -- kernel module
 * Use `make` to compile and `insmod` to load the module
 *
 * Sergiy Lozovsky <sergiy.lozovsky@gmail.com>
 * Peter V. Saveliev <peter@svinota.eu>
 *
 * Tested for RHEL6.5
 */
#include <linux/module.h>       /* Needed by all modules */
#include <linux/kernel.h>       /* Needed for KERN_INFO */
#include <linux/init.h>         /* Needed for the macros */
#include <net/genetlink.h>

/* attributes (variables): the index in this enum is used as a reference for the type,
 *             userspace application has to indicate the corresponding type
 *             the policy is used for security considerations
 *
 * the same for commands: enumeration of all commands (functions), used by userspace
 *                        application to identify command to be ececuted
 */
enum {
        EXMPL_UNSPEC,
        EXMPL_MSG,
        __EXMPL_MAX,
};
#define EXMPL_MAX (__EXMPL_MAX - 1)

/* attribute policy: defines which attribute has which type (e.g int, char * etc)
 * possible values defined in net/netlink.h 
 */
static struct nla_policy exmpl_genl_policy[EXMPL_MAX + 1] = {
        [EXMPL_MSG] = { .type = NLA_NUL_STRING },
};

#define VERSION_NR 1
/* family definition */
static struct genl_family exmpl_gnl_family = {
        .id = GENL_ID_GENERATE,         //genetlink should generate an id
        .hdrsize = 0,
        .name = "EXMPL_GENL",           //the name of this family, used by userspace application
        .version = VERSION_NR,          //version number  
        .maxattr = EXMPL_MAX,
};


/* hello world from the inner space */
int hello_world(struct sk_buff *request, struct genl_info *info)
{
        struct sk_buff *reply;
        int rc;
        void *msg_head;
        
        if (info == NULL)
                goto out;
  
        /* send a message back*/
        /* allocate some memory, since the size is not yet known use NLMSG_GOODSIZE*/   
        reply = genlmsg_new(NLMSG_GOODSIZE, GFP_KERNEL);
        if (reply == NULL)
                goto out;

        msg_head = genlmsg_put_reply(reply, info, &exmpl_gnl_family, 0, info->genlhdr->cmd);
        if (msg_head == NULL) {
                rc = -ENOMEM;
                goto out;
        }
        /* add a EXMPL_MSG attribute (actual value to be sent) */
        rc = nla_put_string(reply, EXMPL_MSG, "hello world from kernel space");
        if (rc != 0)
                goto out;
        
        /* finalize the message */
        genlmsg_end(reply, msg_head);

        /* send the message back */
        rc = genlmsg_reply(reply, info);
        if (rc != 0)
                goto out;
        return 0;

 out:
        printk("an error occured in hello_world:\n");
  
      return 0;
}
/* commands: mapping between the command enumeration and the actual function*/
struct genl_ops exmpl_gnl_ops_echo = {
        .cmd = EXMPL_MSG,
        .flags = 0,
        .policy = exmpl_genl_policy,
        .doit = hello_world,
        .dumpit = NULL,
};

static int __init exmpl_gnl_init(void)
{
        int rc;
        rc = genl_register_family(&exmpl_gnl_family);
        if (rc != 0) {
            printk(KERN_INFO "rkmod: genl_register_family failed %d\n", rc);
            return 1;
        }
        /* genl_register_ops requires old kernels, on latest kernels use
         * genl_register_family_with_ops
         */
        rc = genl_register_ops(&exmpl_gnl_family, &exmpl_gnl_ops_echo);
        if (rc != 0) {
            printk(KERN_INFO "rkmod: genl_register_ops failed %d\n", rc);
            genl_unregister_family(&exmpl_gnl_family);
            return -1;
        }
        printk(KERN_INFO "Generic netlink example loaded, protocol version %d\n", VERSION_NR);
        return 0;
}

static void __exit exmpl_gnl_exit(void)
{
        int ret;
        /*unregister the functions*/
        ret = genl_unregister_ops(&exmpl_gnl_family, &exmpl_gnl_ops_echo);
        if(ret != 0){
                printk("unregister ops: %i\n",ret);
                return;
        }
        /*unregister the family*/
        ret = genl_unregister_family(&exmpl_gnl_family);
        if(ret !=0){
                printk("unregister family %i\n",ret);
        }
}

module_init(exmpl_gnl_init);
module_exit(exmpl_gnl_exit);

MODULE_LICENSE("GPL");
